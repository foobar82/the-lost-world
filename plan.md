# Phase 3: Agent Plugin Framework — Implementation Plan

## Summary

Phase 3 creates the core agent abstraction layer: a base interface, skeleton implementations for all six pipeline agents, an agent registry, and tests. This is the foundation that later phases will flesh out with real logic.

## Current State

- **Phase 1 (Ollama)**: Complete
- **Phase 2 (ChromaDB)**: Complete — `pipeline/utils/embeddings.py` exists with ChromaDB + Ollama embedding utilities; `tests/pipeline/test_embeddings.py` has full test coverage; `backend/app/router_feedback.py` already calls `store_feedback_embedding` on submission
- **Existing pipeline structure**: `pipeline/__init__.py`, `pipeline/utils/__init__.py`, `pipeline/utils/embeddings.py`
- **No agents directory yet** — this is what we're building

## Files to Create

### Step 1: Base Interface — `pipeline/agents/base.py`

Create the abstract base class and data classes that all agents must conform to.

```
pipeline/agents/__init__.py        — empty (package marker)
pipeline/agents/base.py            — AgentInput, AgentOutput, Agent ABC
```

- `AgentInput`: dataclass with `data: Any` and `context: dict`
- `AgentOutput`: dataclass with `data: Any`, `success: bool`, `message: str`, `tokens_used: int`
- `Agent`: ABC with abstract `run(input: AgentInput) -> AgentOutput` method and abstract `name` property

This matches the spec in the plan document exactly (section 3.1).

### Step 2: Skeleton Agent Implementations

Create six agent modules in `pipeline/agents/`, each with a class that inherits from `Agent` and implements the interface with placeholder logic. Each skeleton will:
- Log what it would do
- Return an `AgentOutput` with `success=True`, a descriptive message, and `tokens_used=0`

Files:

1. **`pipeline/agents/filter_agent.py`** — `FilterAgent`
   - `name` = `"filter"`
   - Skeleton logs: "Would classify feedback as safe/harmful via Ollama"
   - Returns `AgentOutput(data={"verdict": "safe", "reason": "placeholder"}, success=True, ...)`

2. **`pipeline/agents/cluster_agent.py`** — `ClusterAgent`
   - `name` = `"cluster"`
   - Skeleton logs: "Would query ChromaDB and cluster pending feedback by similarity"
   - Returns `AgentOutput(data={"clusters": []}, success=True, ...)`

3. **`pipeline/agents/prioritiser_agent.py`** — `PrioritiserAgent`
   - `name` = `"prioritise"`
   - Skeleton logs: "Would select and summarise top clusters via Ollama"
   - Returns `AgentOutput(data={"tasks": []}, success=True, ...)`

4. **`pipeline/agents/writer_agent.py`** — `WriterAgent`
   - `name` = `"write"`
   - Skeleton logs: "Would generate code changes via Anthropic API"
   - Returns `AgentOutput(data={"changes": [], "summary": "", "reasoning": ""}, success=True, ...)`

5. **`pipeline/agents/reviewer_agent.py`** — `ReviewerAgent`
   - `name` = `"review"`
   - Skeleton logs: "Would review code changes via Anthropic API"
   - Returns `AgentOutput(data={"verdict": "approve", "comments": ""}, success=True, ...)`

6. **`pipeline/agents/deployer_agent.py`** — `DeployerAgent`
   - `name` = `"deploy"`
   - Skeleton logs: "Would create branch, apply changes, run CI/CD pipeline, merge"
   - Returns `AgentOutput(data={"branch": "", "deployed": False}, success=True, ...)`

### Step 3: Agent Registry — `pipeline/registry.py`

Create a simple dictionary mapping step names to agent instances:

```python
AGENTS = {
    "filter": FilterAgent(),
    "cluster": ClusterAgent(),
    "prioritise": PrioritiserAgent(),
    "write": WriterAgent(),
    "review": ReviewerAgent(),
    "deploy": DeployerAgent(),
}
```

This provides the modularity point — swapping an agent means changing one line in the registry.

### Step 4: Tests — `tests/pipeline/test_registry.py`

Verify:

1. **All expected agents are registered** — the registry contains exactly the six expected keys: `filter`, `cluster`, `prioritise`, `write`, `review`, `deploy`
2. **Each agent implements the interface** — every registered agent is an instance of `Agent` (the ABC), has a `name` property that returns a non-empty string, and has a callable `run` method
3. **Each agent's `run` method returns an `AgentOutput`** — call `run()` with a minimal `AgentInput` and assert the return type is `AgentOutput` with `success=True`
4. **Swapping an agent works** — replace one entry in the registry with a different `Agent` subclass and verify it's callable

Testing pattern: follow the existing test style from `tests/pipeline/test_embeddings.py` — use `sys.path.insert` for imports, pytest classes, no fixtures needed (agents are simple).

### Step 5: Run Tests and Verify

- Run `python -m pytest tests/pipeline/test_registry.py -v` to confirm all tests pass
- Run `python -m pytest tests/pipeline/ -v` to confirm existing embedding tests still pass
- Optionally run `ruff check pipeline/` for lint compliance

### Step 6: Commit and Push

- Stage all new files
- Commit with a descriptive message
- Push to `claude/plan-phase-3-pipeline-iFM9h`

## Files Changed (Summary)

| File | Action |
|------|--------|
| `pipeline/agents/__init__.py` | Create (empty package marker) |
| `pipeline/agents/base.py` | Create (AgentInput, AgentOutput, Agent ABC) |
| `pipeline/agents/filter_agent.py` | Create (FilterAgent skeleton) |
| `pipeline/agents/cluster_agent.py` | Create (ClusterAgent skeleton) |
| `pipeline/agents/prioritiser_agent.py` | Create (PrioritiserAgent skeleton) |
| `pipeline/agents/writer_agent.py` | Create (WriterAgent skeleton) |
| `pipeline/agents/reviewer_agent.py` | Create (ReviewerAgent skeleton) |
| `pipeline/agents/deployer_agent.py` | Create (DeployerAgent skeleton) |
| `pipeline/registry.py` | Create (AGENTS dict) |
| `tests/pipeline/test_registry.py` | Create (registry + interface tests) |

## Design Decisions

- **Skeleton agents return mock success**: Each `run()` returns a plausible-looking `AgentOutput` so the registry tests and future orchestrator work can call them without errors. Real logic is added in later phases.
- **`tokens_used=0` for skeletons**: No LLM calls in placeholders, so token tracking starts at zero.
- **Follow existing patterns**: The `sys.path.insert` pattern from `test_embeddings.py` is reused for test imports rather than introducing a new approach.
- **No new dependencies**: Phase 3 only uses stdlib (`abc`, `dataclasses`, `logging`, `typing`). No pip installs needed.
