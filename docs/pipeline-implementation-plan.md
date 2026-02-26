# Agent Pipeline — Implementation Plan for Claude Code

## Context

The Lost World Plateau v0 is running on a MacBook M3, with a CI/CD pipeline (lint → type check → tests → build → deploy) in place. The next step is building the agent pipeline that will autonomously process user feedback and generate code changes.

Development happens on the Windows desktop via Claude Code. The pipeline will run in production on the MacBook.

- **API provider:** Anthropic (Claude) — API key already set up
- **Local LLM:** ✅ Ollama running on MacBook — llama3.1:8b and nomic-embed-text models installed and tested
- **SSH tunnel:** ✅ Windows can reach MacBook's Ollama via SSH tunnel (port 11434 forwarded). Connect with: `ssh macbook -N`
- **Database:** ChromaDB installed in backend venv on MacBook, not yet configured
- **Development pattern:** No mock mode for Ollama — Windows dev uses SSH tunnel to MacBook's Ollama. Mocks only used in automated tests.

---

## Phase 1: Ollama Setup and Validation (MacBook) ✅ COMPLETE

Ollama is running on the MacBook with llama3.1:8b (chat/classification) and nomic-embed-text (embeddings) models. SSH tunnel configured from Windows desktop to MacBook (port 11434). Tested and working via both direct access on MacBook and tunnel from Windows.

---

## Phase 2: ChromaDB Setup

### 2.1 Install ChromaDB ✅ COMPLETE

ChromaDB is installed in the backend virtual environment on the MacBook.

```bash
# Already done — activate venv and verify with:
source backend/venv/bin/activate
pip show chromadb
```

### 2.2 Configure ChromaDB  ✅ COMPLETE

ChromaDB will store embeddings of user feedback for clustering. Create a persistent ChromaDB instance that stores data on disk (survives restarts).

Configuration:
- Storage path: `backend/data/chromadb/` (add `backend/data/` to `.gitignore`)
- Collection name: `feedback_embeddings`
- Embedding function: Ollama's nomic-embed-text model via API call

### 2.3 Integration with Feedback Submission ✅ COMPLETE

When a new feedback submission arrives at POST /api/feedback:
1. Save to SQLite (existing behaviour)
2. Generate embedding via Ollama
3. Store embedding in ChromaDB with the feedback reference as the ID

This happens at submission time, not batch time — per the architectural plan.

---

## Phase 3: Agent Plugin Framework ✅ COMPLETE

This is the core abstraction. Each agent is a Python module with a standard interface.

### 3.1 Base Interface ✅ COMPLETE

### 3.2 Agent Implementations ✅ COMPLETE

Create one module per agent in `pipeline/agents/`:

**pipeline/agents/filter_agent.py — Evil Filter**
**pipeline/agents/cluster_agent.py — Clustering**
**pipeline/agents/prioritiser_agent.py — Prioritisation**
**pipeline/agents/writer_agent.py — Code Writer**
**pipeline/agents/reviewer_agent.py — Code Reviewer**
**pipeline/agents/deployer_agent.py — Deployer**

### 3.3 Agent Registry  ✅ COMPLETE

A simple dictionary that maps step names to agent instances. This is where modularity lives — swapping an agent means changing one line in the registry.

---

## Phase 4: Submission-Time Processing

### 4.1 Update Feedback Endpoint

Modify POST /api/feedback to include submission-time processing:

```
1. Validate input
2. Save to SQLite with status "pending"
3. Run filter agent
   - If rejected: update status to "rejected", save agent reason as agent_notes, return response
   - If passed: continue
4. Generate embedding via Ollama
5. Store embedding in ChromaDB
6. Return reference number to user
```

### 4.2 Error Handling

If Ollama is unavailable (e.g. model not loaded, server down):
- Still save the submission to SQLite with status "pending"
- Log the error
- Skip embedding generation — it can be backfilled at batch time
- Do NOT reject the submission just because the local model is down

---

## Phase 5: Daily Batch Script

### 5.1 Batch Orchestrator

Create `pipeline/batch.py` — the main script that runs the daily batch.

```
1. Load config (budget caps, repo path, etc.)
2. Check budget: has the daily cap (£2) or weekly cap (£8) been reached?
   - If yes: log "budget exceeded", update queue status message, exit
3. Get all pending submissions from SQLite
   - If none: log "no pending submissions", exit
4. Backfill any missing embeddings (for submissions where Ollama was down at submission time)
5. Run cluster agent on all pending submissions
6. Run prioritiser agent on the clusters
7. For each prioritised task (until budget is exhausted):
   a. Run writer agent → get proposed changes
   b. Run reviewer agent → approve or reject
      - If rejected: loop back to writer with reviewer feedback (max 2 retries)
      - If still rejected after retries: mark related submissions as "pending" (try again tomorrow), log the failure
   c. If approved: run deployer agent
      - If deployment fails: mark submissions as "pending", log the failure
      - If deployment succeeds: mark related submissions as "done", save agent notes
8. Log summary: tasks attempted, tasks completed, tokens used, budget remaining
```

### 5.2 Budget Tracking

Create `pipeline/budget.py`:

- Track token usage per API call (Anthropic returns this in the response)
- Convert tokens to approximate cost using current pricing
- Store daily/weekly spend in a simple JSON file (`pipeline/data/budget.json`)
- Check against caps before each expensive agent call
- If a call would exceed the remaining budget, skip it and roll the task over

### 5.3 Configuration

Create `pipeline/config.py`:

```python
PIPELINE_CONFIG = {
    "daily_budget_gbp": 2.00,
    "weekly_budget_gbp": 8.00,
    "writer_model": "claude-sonnet-4-20250514",
    "reviewer_model": "claude-sonnet-4-20250514",  # Same model for now, different system prompt
    "local_model": "llama3.1:8b",
    "embedding_model": "nomic-embed-text",
    "ollama_url": "http://localhost:11434",
    "max_writer_retries": 2,
    "repo_path": "/path/to/lost-world",  # Set per environment
    "contract_file": "contract.md",
}
```

### 5.4 Running the Batch

For now, manually triggered:

```bash
cd pipeline
python batch.py
```

Automation via cron comes in month 2 (per the roadmap). For now, you trigger it manually to observe and learn.

---

## Phase 6: Writer Agent — Deep Dive

The writer agent is the most complex and highest-risk agent. It deserves extra attention.

### 6.1 Context Engineering

The writer agent needs to send Claude enough context to make good changes, but not so much that it's expensive or confused. For each task:

1. **Always include:** the contract file, the simulation config, and the task summary
2. **Selectively include:** only the source files relevant to the task
3. **Never include:** test files, config files, node_modules, build output

Strategy for selecting relevant files:
- Start simple: include all source files (the codebase is small right now)
- Add smarter file selection later if the codebase grows and costs increase

### 6.2 Output Format

The writer agent should return changes as a structured format that the deployer can apply:

```python
@dataclass
class FileChange:
    path: str            # Relative to repo root
    action: str          # "create", "modify", "delete"
    content: str         # New file content (for create/modify)
    
@dataclass 
class WriterOutput:
    changes: list[FileChange]
    summary: str         # Human-readable description of what was changed
    reasoning: str       # Why these changes were made
```

The deployer agent then applies these changes, commits, and runs the pipeline.

### 6.3 System Prompt

The writer agent's system prompt should:
- Explain the project context briefly
- Reference the contract file as inviolable constraints
- Instruct it to return changes in the structured format
- Emphasise: make minimal, focused changes; don't refactor unrelated code; ensure existing tests still pass
- Include the task summary and relevant source files as user message content

---

## Phase 7: Validation

### 7.1 Unit Tests for the Pipeline

Create `tests/pipeline/`:

**test_filter_agent.py:**
- Safe request → passes
- Obviously harmful request ("make this a spam bot") → rejected
- Edge case request → handled without crashing

**test_budget.py:**
- Track spending → correctly accumulates
- Daily cap hit → blocks further calls
- Weekly cap hit → blocks further calls
- New day → daily budget resets (weekly doesn't)

**test_registry.py:**
- All expected agents are registered
- Each agent implements the standard interface
- Swapping an agent in the registry works

### 7.2 Integration Test

**test_batch.py:**
- Create test feedback submissions
- Run the batch with mocked LLM responses (don't burn real API credits on tests)
- Assert: submissions are clustered, prioritised, and processed in the correct order
- Assert: budget tracking works end to end
- Assert: submission statuses are updated correctly

### 7.3 End-to-End Validation Checklist

- [ ] Submit a feedback request via the app → it's saved, filtered, and embedded
- [ ] Run batch.py manually → it picks up the pending request
- [ ] Writer agent generates sensible code changes
- [ ] Reviewer agent reviews and approves (or rejects with feedback)
- [ ] Deployer agent creates a branch, applies changes, runs the pipeline, and merges
- [ ] The app is redeployed with the changes
- [ ] The feedback submission status is updated to "done" with agent notes
- [ ] Budget tracking reflects the tokens used
- [ ] Submitting a harmful request → it's filtered and rejected at submission time

---

## Phased Prompts for Claude Code

Use these sequentially, reviewing between each.

### Prompt 1: Plugin Framework
```
Read docs/pipeline-plan.md for the full implementation plan.

Implement Phase 3: the agent plugin framework.

Create the base interface (pipeline/agents/base.py) with AgentInput, AgentOutput, and the abstract Agent class. Then create skeleton implementations for all six agents (filter, cluster, prioritiser, writer, reviewer, deployer) — each in its own module under pipeline/agents/. The skeletons should implement the interface with placeholder logic that logs what it would do and returns a mock success response.

Create the agent registry (pipeline/registry.py) that maps step names to agent instances.

Add a simple test (tests/pipeline/test_registry.py) that verifies all agents are registered and implement the interface correctly.

Commit when done.
```

### Prompt 2: ChromaDB and Embedding
```
Read docs/pipeline-plan.md Phase 2 for specifications.

Install ChromaDB and set up the embedding pipeline.

- ChromaDB is already installed in the backend venv — verify with pip show chromadb
- Create a persistent ChromaDB instance storing data in backend/data/chromadb/ (add backend/data/ to .gitignore)
- Create a collection called "feedback_embeddings"
- Write a utility module (pipeline/utils/embeddings.py) that:
  - Calls Ollama's nomic-embed-text model to generate embeddings (Ollama runs on localhost:11434, accessible from both MacBook directly and Windows via SSH tunnel)
  - Stores embeddings in ChromaDB with the feedback reference as ID
  - Has a fallback that logs an error if Ollama is unavailable (does not crash)

Write tests for the embedding utility using mocked Ollama responses (don't require a running Ollama instance in tests).

Commit when done.
```

### Prompt 3: Filter Agent and Submission-Time Processing
```
Read docs/pipeline-plan.md Phases 3 and 4 for specifications.

Implement the filter agent and integrate submission-time processing into the feedback endpoint.

Filter agent (pipeline/agents/filter_agent.py):
- Uses Ollama (local model) to classify whether a feedback submission is safe or harmful
- Returns pass/reject with a reason
- If Ollama is unavailable, defaults to passing the submission (don't block users because the local model is down)

Update POST /api/feedback to:
1. Save to SQLite
2. Run filter agent — if rejected, update status to "rejected" with agent_notes, return response
3. If passed, generate embedding and store in ChromaDB
4. Return reference number

On Windows dev, Ollama is accessible via SSH tunnel on localhost:11434. Test both pass and reject paths using mocked responses in automated tests.

Commit when done.
```

### Prompt 4: Cluster, Prioritiser, and Budget Tracking
```
Read docs/pipeline-plan.md Phases 3 and 5 for specifications.

Implement the cluster agent, prioritiser agent, and budget tracking.

Cluster agent (pipeline/agents/cluster_agent.py):
- Queries ChromaDB for all pending submission embeddings
- Groups by similarity (use ChromaDB's similarity search with a distance threshold)
- Returns clusters ordered by size, largest first

Prioritiser agent (pipeline/agents/prioritiser_agent.py):
- Takes clusters from the cluster agent
- Uses Ollama to generate a brief task summary for each cluster
- Selects top cluster(s) that fit within the remaining daily budget
- Returns prioritised task list with summaries

Budget tracking (pipeline/budget.py):
- Tracks token usage per API call, converts to approximate GBP cost
- Stores daily/weekly spend in pipeline/data/budget.json
- Provides check_budget() function that returns remaining daily and weekly budget
- Daily budget resets at midnight, weekly resets on Monday

Write tests for budget tracking (reset logic, cap enforcement). Mock LLM calls for cluster and prioritiser tests.

Commit when done.
```

### Prompt 5: Writer, Reviewer, and Deployer
```
Read docs/pipeline-plan.md Phases 3 and 6 for specifications.

Implement the writer, reviewer, and deployer agents. These are the most critical agents in the pipeline.

Writer agent (pipeline/agents/writer_agent.py):
- Uses Anthropic API (Claude)
- Receives a task summary and relevant source files as context
- Always includes the contract file in the prompt
- System prompt instructs: make minimal, focused changes; don't refactor unrelated code; ensure existing tests still pass
- Returns structured FileChange objects (path, action, content) plus a summary and reasoning
- Tracks and reports token usage

Reviewer agent (pipeline/agents/reviewer_agent.py):
- Uses Anthropic API (Claude) with a different system prompt from the writer
- Receives the proposed changes from the writer
- Reviews for correctness, security, and adherence to the contract file
- Returns approve/reject with comments
- If rejected, includes specific feedback that can be passed back to the writer

Deployer agent (pipeline/agents/deployer_agent.py):
- Deterministic (no LLM)
- Creates a feature branch, applies FileChange objects, commits
- Runs scripts/pipeline.sh
- If pipeline passes: merges to main, runs deployment
- If pipeline fails: reports the failure, does not merge
- Returns success/failure with details

Write integration tests with mocked API responses. Do not make real API calls in tests.

Commit when done.
```

### Prompt 6: Batch Orchestrator and Validation
```
Read docs/pipeline-plan.md Phase 5 for specifications.

Implement the batch orchestrator and validate the full pipeline.

Create pipeline/batch.py:
- Load config, check budget
- Get pending submissions, backfill any missing embeddings
- Run cluster → prioritise → for each task: write → review (with retry loop, max 2) → deploy
- Update submission statuses throughout
- Log a summary at the end (tasks attempted, completed, tokens used, budget remaining)

Create pipeline/config.py with all configuration values.

Then validate:
- Write an integration test (tests/pipeline/test_batch.py) that runs the full batch with mocked LLM responses and asserts correct behaviour end to end
- Run the pipeline unit tests to make sure everything still passes

Do NOT run a real batch against the API yet — we'll do that manually after review.

Commit when done.
```

---

## After All Prompts

1. Review the complete pipeline code
2. Deploy to the MacBook
3. Test Ollama integration (filter and embedding) with real requests
4. Run one real batch manually, observing each step
5. Submit the known bugs and desired changes as feedback and let the pipeline process them

---

## Notes for Claude Code

- The pipeline/ directory is a new top-level directory in the monorepo
- All LLM calls in tests must be mocked — never burn real API credits in automated tests
- Ollama is accessible on localhost:11434 from both machines (directly on MacBook, via SSH tunnel on Windows) — no mock mode needed outside of tests
- The writer agent is the most complex — spend extra care on its system prompt and output parsing
- The deployer agent interacts with git — make sure it handles dirty working directories and branch conflicts gracefully
- Budget tracking must be persistent (survives process restarts) and accurate — this directly controls spend
- Keep agent implementations focused and simple — the modularity is in the registry, not in each agent
- Remember to activate the backend venv (source backend/venv/bin/activate) before running any Python pipeline code