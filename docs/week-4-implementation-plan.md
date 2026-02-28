# Week 4: Close the Loop — Implementation Plan

## Context

Weeks 1-3 are complete. The app is running on the MacBook, the CI/CD pipeline is in place, and the agent pipeline is built. Several feedback submissions are pending in the queue. This week is about connecting everything and achieving minimum success: one user-submitted change refined and deployed by the agents.

---

## Phase 1: Write the Contract File

This is a human task, not a Claude Code task. The contract file defines the invariants the agents must respect. It's referenced by the writer and reviewer agents in their prompts.

### 1.1 Create contract.md - COMPLETE

Based on the planning document, the contract should include:

**Identity and purpose**
**Structural invariants**
**Security invariants**
**Technical invariants**
**What agents must NOT do**

---

## Phase 2: Review Existing Tests

Before adding essential tests, understand what's already covered. This is a Claude Code task.

---

## Phase 3: Essential Test Suite

Based on the test review, add any missing essential tests. These are the human-maintained tests that must always pass regardless of how the app evolves. They validate the contract file invariants programmatically.

---

## Phase 4: Dry Run

Before running the real pipeline, do a dry run to catch configuration issues without burning API credits. This runs on the MacBook.

---

## Phase 5: First Real Batch

The moment of truth. Run batch.py for real on the MacBook with pending feedback submissions.

---

## Phase 6: Validate and Document

Verify the deployment worked and capture the milestone.

---

## Prompts for Claude Code

### Prompt 1: Review Existing Tests

```
I'm preparing to close the loop on my agentic architecture experiment. Before adding new tests, I need to understand what's already covered.

Review all existing tests across the project:
- List every test file and briefly summarise what each test covers
- Identify which of the following are already tested and which are not:
  1. App renders without crashing
  2. Ecosystem canvas is present and initialises
  3. Simulation ticks at the expected rate
  4. All three species (plants, herbivores, predators) are present at initialisation
  5. Entities stay within plateau bounds
  6. Feedback text box is present and functional
  7. POST /api/feedback creates a record and returns a reference number
  8. GET /api/feedback returns submissions
  9. GET /api/feedback/{reference} returns the correct item
  10. Request queue displays pending items
  11. All API endpoints return valid responses (no 500 errors on valid input)
  12. Frontend builds without errors
  13. Backend starts without errors

Report back with: what's covered, what's missing, and any tests that are broken or skipped.

Do not make any changes yet.
```

### Prompt 2: Essential Test Suite

```
Based on your review of existing tests, create or update the essential test suite.

Read contract.md for the invariants these tests must validate.

Create tests/essential/ as a dedicated directory for human-maintained essential tests. These tests must:

Frontend (tests/essential/test_app_essentials.ts):
- App renders without crashing
- Ecosystem canvas element is present
- Feedback text box is present and accepts input
- Request queue component is present
- No console errors on initial load

Simulation (tests/essential/test_simulation_essentials.ts):
- Simulation ticks at approximately the expected rate (the tick bug guard)
- All three species exist at initialisation
- Entities stay within plateau bounds after 100 ticks
- Ecosystem doesn't collapse to extinction within 500 ticks

Backend (tests/essential/test_api_essentials.py):
- POST /api/feedback with valid content returns 200 with reference and status
- GET /api/feedback returns a list
- GET /api/feedback/{reference} returns the correct item
- POST /api/feedback with empty content returns an error (not 500)
- Backend starts and serves the health check (or root endpoint) without errors

Do NOT duplicate tests that already exist and are working. If an existing test already covers one of these, note it and skip it. Only add what's missing.

If any existing tests are broken, fix them.

Add a comment block at the top of each essential test file:
# ESSENTIAL TESTS - Human-maintained only
# These tests validate contract.md invariants
# Agents must not modify these files

Update scripts/pipeline.sh to run the essential tests as a separate, clearly labelled step.

Commit when done.
```

### Prompt 3: Dry Run Preparation

```
I'm about to run batch.py for the first time on the MacBook. Before I do a real run with API credits, I want to verify the pipeline works end to end without calling external APIs.

Create a dry run mode for batch.py that:
- Accepts a --dry-run flag
- Runs the full pipeline flow (read queue → cluster → prioritise → write → review → deploy)
- For local Ollama calls (filter, cluster, embedding): makes real calls (these are free)
- For Anthropic API calls (writer, reviewer): logs what it would send and returns a mock response that includes a trivial, safe code change (e.g. adding a comment to a file)
- For deployment: logs what it would do but does not create branches, commit, or deploy
- Prints a full summary at the end: submissions processed, clusters found, tasks prioritised, mock changes generated, budget that would have been used

This lets me verify the flow, the Ollama integration, the ChromaDB queries, and the budget tracking without spending money.

Commit when done.
```

### Prompt 4: Dry Run Fixes

```
I've run batch.py --dry-run on the MacBook. Here are the issues I found:

[INSERT ISSUES HERE]

Fix each issue. Run the dry run again after fixes to verify. Commit when done.
```

(Use this prompt if the dry run surfaces problems. Skip if it runs cleanly.)

### Prompt 5: Post-Run Validation

```
The first real batch has been run. Verify the results:

1. Check git log — are there new commits from the agent on a feature branch or main?
2. Check the feedback submissions in the database — have any been updated to status "done" with agent_notes?
3. Check the budget tracking file — does it reflect the tokens used?
4. Run scripts/pipeline.sh — does the full CI/CD pipeline still pass with the agent's changes?
5. Check the deployed app — does it load and function correctly?
6. Review the agent's code changes — are they sensible, minimal, and aligned with the contract file?

Report what you find. Do not make any changes.
```

---

## Manual Steps (Not Claude Code)

### Write the Contract File

Create contract.md in the repo root using the content from Phase 1 above. Review and adjust to match your actual app. Commit.

### Submit Terms of Service and Privacy Policy

If these aren't already in the app, create minimal versions and add them. These become protected by the contract file. The agents can style them but not change the content.

### Run the Dry Run (MacBook)

```bash
cd /path/to/lost-world
source backend/venv/bin/activate
python pipeline/batch.py --dry-run
```

Review the output. If there are issues, use Prompt 4 with Claude Code to fix them.

### Run the First Real Batch (MacBook)

Once the dry run is clean:

```bash
python pipeline/batch.py
```

Watch the output carefully. This is the first time real API credits are being spent and real code changes are being generated. Take notes for your blog post.

After it completes, use Prompt 5 with Claude Code to validate the results.

### Celebrate

If at least one feedback submission has been processed, refined, and deployed by the agents — you've achieved minimum success. Write it up.

---

## Blog Post Notes

Capture during this week:
- What the dry run revealed (there will be surprises)
- What the first real batch produced
- How the agent's code changes compared to what you would have written
- Whether the reviewer caught anything the writer got wrong
- Budget spent vs. budget estimated
- How it felt watching agents deploy to your live app

This is blog post #3 or #4 material — "Closing the Loop: The First Autonomous Deployment."
