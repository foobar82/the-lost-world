# Code Review — The Lost World Plateau

**Date:** 2026-02-26
**Scope:** Full codebase review against spec documents

---

## Architectural Understanding

Before reviewing code, I internalised the spec documents (`docs/agentic-experiment-plan.md`, `docs/pipeline-implementation-plan.md`, `docs/cicd-implementation-plan.md`, `docs/week-2-implementation-plan.md`, `contract.md`, `docs/DEPLOYMENT.md`). The intended architecture, in brief:

- **A 2D ecosystem simulator** rendered on HTML Canvas, evolving daily through user feedback — the app is a vehicle for an experiment in agentic architecture.
- **Core feedback loop:** users submit text requests → an agent pipeline filters, clusters, prioritises, writes code, reviews it, and deploys — all autonomously.
- **Six agents** with a standard interface (`Agent` ABC, `run(AgentInput) → AgentOutput`), registered in a swappable registry. Local LLM (Ollama) handles cheap tasks (filtering, embedding, summarisation); API models (Anthropic Claude) handle expensive tasks (code writing, code review).
- **CI/CD pipeline** (`scripts/pipeline.sh`): lint → typecheck → test → build. A pre-push git hook prevents broken code reaching the remote. The deployer agent creates feature branches, runs the pipeline, and merges on success.
- **Budget tracking** with daily (£2) and weekly (£8) caps, enforced before every expensive API call.

This is my reference frame for the review that follows.

---

## 1. Executive Summary

The codebase is well-structured, cleanly written, and faithfully implements the Week 2 app and the Phase 3 agent pipeline framework. The simulation engine is properly decoupled from rendering, the agent interface is modular and testable, and the test suite is behavioural rather than implementation-coupled. The biggest strength is the clean separation of concerns — simulation logic, canvas rendering, API layer, and agent pipeline each live in their own well-defined boundary. The biggest risk is that the CI pipeline does not run the pipeline agent tests, meaning autonomous code changes to the agent system itself would go unvalidated before merge.

---

## 2. Spec Alignment

### Implemented and Consistent with Spec

- Ecosystem with plants, herbivores, and predators, bounded plateau, water source — matches `week-2-implementation-plan.md` §2.
- Energy system (eat, move, reproduce, die) — matches §2.2–2.4.
- Feedback submission (POST), queue display (GET), reference numbers (LW-NNN) — matches §3.
- Simulation decoupled from rendering into `simulation/` module — matches `cicd-implementation-plan.md` §5.
- Agent plugin framework with base interface, six skeleton-then-real agents, registry — matches `pipeline-implementation-plan.md` §3.
- Submission-time filtering and embedding — matches §4.
- Budget tracking with daily/weekly caps — matches §5.2.
- CI/CD pipeline script with lint, typecheck, test, build — matches `cicd-implementation-plan.md` §4.

### Divergences from Spec

| Spec requirement | Status | Notes |
|---|---|---|
| Contract file with real invariants | **Placeholder** | `contract.md` still reads "To be defined in week 4." The writer and reviewer agents read it, but it provides no actual constraints. |
| Pipeline tests in CI | **Missing** | `cicd-implementation-plan.md` §4.1 lists backend tests; `scripts/pipeline.sh` runs only `tests/backend/`, not `tests/pipeline/`. |
| `scripts/deploy.sh` restarts the server | **Placeholder** | Lines 18–20 print a message but do not restart. The deployer agent calls this script (`deployer_agent.py:49`), so autonomous deployments silently fail to restart. |
| Rate limiting by IP/session token | **Not implemented** | Specified in `agentic-experiment-plan.md` §Legal & Ethical. Deferred to month 3 per `week-2-implementation-plan.md` §6.2 — intentional. |
| Terms of service / privacy policy | **Not implemented** | Same — intentionally deferred. |
| Essential test suite (human-maintained) | **Not implemented** | Specified as `tests/essential/` in §1.1 of the week-2 plan; directory does not exist. |
| Writer/reviewer use different models | **Same model** | Spec says "different underlying models for writer and reviewer to avoid correlated blind spots" (`agentic-experiment-plan.md` §Multi-Agent Review). Both use `claude-sonnet-4-20250514`. Config supports swapping, so this is a configuration change, not a code change. |
| `tests/` directory structure | **Partially divergent** | Spec shows `tests/frontend/`, `tests/backend/`, `tests/essential/`. Tests exist at these paths (minus `essential/`). Pipeline tests live at `tests/pipeline/` which is a sensible addition not in the original structure. |

None of the unimplemented items are alarming — they align with the phased roadmap. The two operational divergences (pipeline tests not in CI, deploy restart placeholder) are the ones that need attention before the agentic loop runs unsupervised.

---

## 3. Critical Issues

### 3.1 Pipeline Tests Not Run by CI

**File:** `scripts/pipeline.sh`
**Lines:** 19–20

The pipeline script runs backend tests:

```bash
cd "$REPO_ROOT/backend" && python -m pytest "$REPO_ROOT/tests/backend/" -q
```

But never runs `tests/pipeline/`. There are 10 pipeline test files with substantial coverage of the agent system. When the deployer agent runs `scripts/pipeline.sh` on a feature branch, pipeline code changes pass without test validation.

**Impact:** An agent-generated change that breaks the pipeline itself (e.g., a malformed agent output format) would be merged and deployed.

**Fix:** Add a step between the backend tests and the frontend build:

```bash
echo "=== Step 5.5/7: Pipeline Tests ==="
cd "$REPO_ROOT" && python -m pytest tests/pipeline/ -q
```

### 3.2 Deploy Script Server Restart Is a No-Op

**File:** `scripts/deploy.sh:18–20`

```bash
# TODO: Replace with the actual restart mechanism (systemd, pm2, process manager, etc.)
echo "=== Restarting server (placeholder) ==="
```

The deployer agent (`deployer_agent.py:154–155`) runs this script after merging. Since it does not actually restart anything, the old process continues serving stale code.

**Impact:** Autonomous deployments appear to succeed (the script exits 0) but the running server never picks up the changes.

**Fix:** Implement the restart. On the MacBook production server, this likely means `pkill -f uvicorn && nohup uvicorn ...` or a systemd unit restart. The root-level `deploy.sh` uses `exec uvicorn` which is fine for initial start but not for restarts triggered by the deployer.

### 3.3 SPA Catch-All Has No Path Containment Check

**File:** `backend/app/main.py:42–47`

```python
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    file = _static_path / full_path
    if file.is_file():
        return FileResponse(file)
    return FileResponse(_static_path / "index.html")
```

The `full_path` parameter is joined to `_static_path` without verifying the resolved path remains within the static directory. While most HTTP servers and clients normalise `..` sequences in URLs, percent-encoded traversal sequences (`%2e%2e`) may survive to the application layer depending on server configuration.

**Impact:** Potential directory traversal allowing access to files outside the static directory.

**Fix:**

```python
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    file = (_static_path / full_path).resolve()
    if file.is_file() and file.is_relative_to(_static_path.resolve()):
        return FileResponse(file)
    return FileResponse(_static_path / "index.html")
```

### 3.4 Deployer Agent Does Not Validate File Paths

**File:** `pipeline/agents/deployer_agent.py:206–214`

```python
path = root / change["path"]
...
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(content)
```

The writer agent produces file paths that the deployer applies to disk. If the writer (an LLM) hallucinates a path like `../../etc/crontab`, the deployer would create and write that file. The reviewer agent should catch this, but defence-in-depth requires validation at the point of file system access.

**Impact:** An LLM-generated path traversal could write files outside the repository.

**Fix:** After computing `path`, resolve it and check containment:

```python
resolved = path.resolve()
if not resolved.is_relative_to(root.resolve()):
    return {"success": False, "error": f"Path escapes repository: {change['path']}"}
```

---

## 4. Architecture & Design

### What Works Well

**Simulation decoupled from rendering.** The `simulation/` module (`types.ts`, `constants.ts`, `entities.ts`, `simulation.ts`) is fully independent of React and Canvas. The `Simulation` class exposes a pure `tick()` method and entity state. `EcosystemCanvas.tsx` is a thin rendering layer that reads state and draws. This was a key requirement from the CI/CD plan (§5) and it's done correctly.

**Agent interface is clean and modular.** `AgentInput`/`AgentOutput` dataclasses plus the `Agent` ABC in `pipeline/agents/base.py` provide a clear contract. The registry (`pipeline/registry.py`) maps step names to instances, making agent swapping trivial. Each agent is a standalone module with no coupling to other agents.

**Fixed-timestep physics loop.** `EcosystemCanvas.tsx:209–223` uses an accumulator pattern that correctly decouples simulation ticks (10/s) from frame rate. The `MAX_CATCHUP_TICKS` guard (line 204) prevents runaway ticking when a tab is backgrounded. This is textbook game loop design.

**Pre-rendered background.** Lines 193–201 create an offscreen canvas for the static plateau/water, eliminating per-frame grass texture regeneration. Good performance optimisation.

**Budget-aware pipeline.** Budget checks before every expensive API call (`writer_agent.py:135`, `reviewer_agent.py:109`, `batch.py:180`) ensure the system respects cost caps. The `budget.py` module tracks spend persistently via a JSON file with daily/weekly reset logic.

### Issues

**Code duplication across writer and reviewer agents.** Both `writer_agent.py:49–54` and `reviewer_agent.py:50–55` contain identical `_read_contract()` functions. Both also contain identical markdown-fence-stripping logic (`writer_agent.py:95–103`, `reviewer_agent.py:76–82`). Extract these into a shared utility (e.g., `pipeline/utils/parsing.py`).

**Configuration scattered across modules.** `OLLAMA_URL` is hardcoded in `filter_agent.py:11`, `prioritiser_agent.py:12`, and `embeddings.py:11` as module-level defaults, whilst `pipeline/config.py` centralises these values. Agents do read from context at runtime (e.g., `filter_agent.py:65`), so the defaults are only fallbacks — but having the same string in four places is a maintenance risk.

**Hardcoded CORS origin.** `main.py:18` allows only `http://localhost:5173`. In production, the frontend is served by FastAPI itself (same origin), so CORS is not needed. But the middleware is active unconditionally and will reject legitimate cross-origin requests if the deployment model changes. Consider making this configurable via environment variable, or only applying CORS middleware when `LOST_WORLD_STATIC` is not set (i.e., dev mode).

**No database migrations.** Schema creation uses `Base.metadata.create_all()` at import time (`main.py:12`). This works for the current single-table schema but will cause pain when the schema evolves — `create_all()` does not alter existing tables. Alembic integration would be prudent before the agent pipeline starts modifying the codebase.

**`git add -A` in deployer.** `deployer_agent.py:93` stages everything in the working tree. The deployer does check for a clean working directory first (lines 53–60), so stale untracked files shouldn't be present. But if the writer creates unexpected files (build artefacts, temporary files), they'd be committed. Consider staging only the specific paths from the changes list.

---

## 5. Code Quality & Maintainability

### Python

**Generally clean and idiomatic.** Pydantic schemas, SQLAlchemy mapped columns, FastAPI dependency injection, and dataclasses are all used appropriately.

**Unconventional import in `budget.py:29`:**

```python
monday = now.date() - __import__("datetime").timedelta(days=now.weekday())
```

`timedelta` is available from the `datetime` module already imported on line 5. This should be `from datetime import datetime, timedelta, timezone` at the top of the file.

**Broad exception handling.** Several files use bare `except Exception` where more specific types would aid debugging:

| File | Line(s) | Caught | Should catch |
|---|---|---|---|
| `router_feedback.py` | 47 | `Exception` | `httpx.HTTPError`, `KeyError`, `RuntimeError` |
| `router_feedback.py` | 62 | `Exception` | `httpx.HTTPError`, `chromadb.errors.*` |
| `cluster_agent.py` | 38, 99 | `Exception` | `chromadb.errors.*`, `KeyError` |
| `embeddings.py` | 74 | `Exception` | `chromadb.errors.*` |
| `deployer_agent.py` | 183 | `Exception` | Already best-effort cleanup; acceptable |

The `router_feedback.py` cases are intentionally broad (the spec says "don't block the user"), which is reasonable, but `logger.exception()` is used correctly in all cases, so diagnostic information is preserved.

**Filter agent `success` semantics.** When Ollama is down, `filter_agent.py:89–94` returns `success=True` with a "defaulted to safe" message. This follows the spec ("do NOT reject the submission just because the local model is down") but makes infrastructure failures invisible to monitoring. Consider adding a separate field (e.g., `degraded: bool`) to `AgentOutput`, or at minimum logging at `ERROR` rather than `WARNING` level.

### TypeScript

**Excellent type safety.** `tsconfig.app.json` enables strict mode, `noUnusedLocals`, `noUnusedParameters`, and `noUncheckedSideEffectImports`. ESLint enforces `no-explicit-any`. No `any` types appear anywhere in the source.

**Hardcoded spawn radii.** Herbivore and predator offspring spawn distances are hardcoded at `entities.ts:212` (20 units) and `entities.ts:259` (25 units), whilst the plant spawn radius correctly uses the `PLANT_SPAWN_RADIUS` constant. Extract these to `constants.ts` as `HERBIVORE_SPAWN_RADIUS` and `PREDATOR_SPAWN_RADIUS`.

**Page title.** `frontend/index.html:7` has `<title>frontend</title>`. Should be `<title>The Lost World Plateau</title>`.

### Dead Code / TODOs

| Location | Note |
|---|---|
| `scripts/deploy.sh:18` | `# TODO: Replace with the actual restart mechanism` — covered in §3.2 |
| `contract.md` | "To be defined in week 4" — needs content before the pipeline runs unsupervised |

No dead code was found. The codebase is lean.

---

## 6. Test Coverage & Gaps

### What's Tested Well

**Backend API** (`tests/backend/test_api.py`, 291 lines): Covers feedback creation, validation (empty content, oversized content), reference generation, status filtering, 404 handling, and integration with the filter agent and embedding pipeline via mocks. Tests are behavioural — they exercise HTTP endpoints, not internal functions.

**Simulation engine** (`tests/frontend/simulation.test.ts`, 241 lines): Covers tick rate accuracy (accumulator pattern), entity lifecycle (species survival over 100 ticks), ecosystem stability (500-tick run), and boundary enforcement. Good use of the decoupled `Simulation` class directly.

**Pipeline agents** (6 test files, ~1,700 lines total): Each agent has dedicated tests covering happy path, error handling, and edge cases. Budget enforcement is tested per-agent. Mocked LLM responses are used throughout — no real API calls.

**Batch orchestrator** (`tests/pipeline/test_batch.py`, 663 lines): Covers the full pipeline flow, budget exhaustion mid-batch, write→review retry loop (including the feedback passback), deployment failure rollback, and multi-task processing.

**Feedback panel** (`tests/frontend/feedback.test.tsx`, 174 lines): Covers submission flow, queue display, status badges, and agent notes rendering with mocked API.

### What's Not Tested

| Gap | Severity | Notes |
|---|---|---|
| Pipeline tests not in CI | **Critical** | See §3.1. Tests exist but don't run in the pipeline. |
| Path traversal in SPA catch-all | High | No test for `..` sequences in `serve_spa`. |
| Path traversal in deployer `_apply_changes` | High | No test for file paths that escape the repo root. |
| Predator-prey interaction specifics | Medium | Simulation tests verify survival, not hunting/energy-transfer mechanics. |
| Plant reproduction mechanics | Medium | No test that plants actually reproduce or that density limits work. |
| Concurrent feedback submission | Medium | No test for race conditions on reference number generation (`LW-NNN`). |
| Canvas rendering correctness | Low | `canvas.test.tsx` only verifies no-throw with a stubbed context. Acceptable for canvas — visual testing is better done manually or with screenshot diffing. |
| Network error handling in frontend | Low | `FeedbackPanel` catches errors but no test exercises the error display path. |

### Test Quality Assessment

Tests are overwhelmingly behavioural. The backend tests call HTTP endpoints, the simulation tests call `tick()` and inspect state, the pipeline tests call `agent.run()` with structured inputs. There is very little testing of implementation details (no mocking of internal private methods, no asserting on internal state that isn't part of the public interface). This is the right approach — it means tests won't break when internals are refactored.

The one weakness is the simulation test tolerances. `simulation.test.ts:52–54` allows 8–12 ticks for 1 second of simulated time (target: 10). That's a ±20% margin. The accumulator logic is deterministic, so this should be exact — the tolerance suggests the test was written before the accumulator was implemented and hasn't been tightened since.

---

## 7. Quick Wins

These can each be done in under 15 minutes:

1. **Add pipeline tests to CI** — one line in `scripts/pipeline.sh`. (§3.1)
2. **Fix `index.html` title** — change `<title>frontend</title>` to `<title>The Lost World Plateau</title>`. (`frontend/index.html:7`)
3. **Add path containment check to SPA catch-all** — two-line change in `main.py:44–46`. (§3.3)
4. **Fix `__import__` in `budget.py`** — replace line 29 with a proper `timedelta` import. (`pipeline/budget.py:5, 29`)
5. **Extract spawn radii to constants** — add `HERBIVORE_SPAWN_RADIUS = 20` and `PREDATOR_SPAWN_RADIUS = 25` to `constants.ts`, reference them in `entities.ts:212, 259`.
6. **Add path containment check to deployer** — four lines in `deployer_agent.py:207`. (§3.4)

---

## 8. Recommended Next Steps

### Small (< 1 hour)

1. **Add pipeline tests to `scripts/pipeline.sh`** — critical for autonomous operation.
2. **Fix the three path safety issues** (SPA catch-all, deployer `_apply_changes`, `git add -A` → specific paths).
3. **Fix `index.html` title** and the `budget.py` import.
4. **Extract hardcoded constants** (spawn radii in `entities.ts`).
5. **Make CORS origin configurable** via environment variable, or disable CORS middleware in production mode.

### Medium (1–4 hours)

6. **Implement the deploy script restart mechanism** (`scripts/deploy.sh`). Without this, the deployer agent's merge-and-deploy flow is broken for production. Decide on process management (systemd, pm2, or a simple PID-file approach) and implement it.
7. **Extract shared utilities** for contract reading and markdown fence stripping from `writer_agent.py` and `reviewer_agent.py` into `pipeline/utils/`.
8. **Write the contract file** (`contract.md`). The writer and reviewer agents already read it; it needs actual invariants before the loop runs unsupervised. At minimum: "the app must have a landing page", "all API routes must remain reachable", "user submissions must not be exposed to other users' sessions", "the feedback mechanism must always be accessible".
9. **Add the missing test cases**: path traversal in deployer, predator-prey interaction in simulation, concurrent submission race condition.
10. **Centralise configuration** — have agents read from `PIPELINE_CONFIG` rather than module-level defaults for `OLLAMA_URL`, `CHAT_MODEL`, etc.

### Large (> 4 hours)

11. **Add Alembic for database migrations.** Currently `create_all()` handles schema creation, but any future column additions or type changes will require manual migration. Set this up before the agent pipeline starts modifying the backend.
12. **Implement rate limiting** on the feedback endpoint. The spec calls for IP/session-based rate limiting (month 3 scope). FastAPI middleware or a simple in-memory token bucket would suffice initially.
13. **Create the `tests/essential/` suite** — human-maintained invariant tests that codify the contract file as executable assertions. These should run regardless of what the agents change.
14. **Set up observability** — the spec calls for build/bundle size tracking, Lighthouse scores, and error rate monitoring. Even lightweight versions (log bundle size per deploy, run Lighthouse in CI) would provide early warning of degradation.

---

*Review conducted against commit on `main` as of 2026-02-26. All file paths and line numbers reference the current state of the codebase.*
