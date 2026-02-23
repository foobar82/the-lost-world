# CI/CD Pipeline & Test Harness — Implementation Plan for Claude Code

## Context

The Lost World Plateau v0 is running on a MacBook M3 exposed via Cloudflare Tunnel. There are known bugs and desired changes logged as feedback submissions. Before building the agent framework, we need the deployment pipeline and test harness that both humans and agents will use.

The monorepo is already set up with a React TypeScript frontend and FastAPI backend.

---

## Phase 1: Test Harness — Frontend

### 1.1 Test Framework Setup

Install and configure Vitest (pairs naturally with Vite) and React Testing Library.

```bash
cd frontend
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom
```

Configure Vitest in `vite.config.ts` with jsdom environment.

### 1.2 Simulation Tests

These are the critical tests that would have caught the tick bug. Create `tests/frontend/simulation.test.ts`:

**Tick rate:**
- Initialise the simulation engine (decoupled from the canvas — if it isn't already, this is a refactor to do first)
- Call update in a loop simulating 1 second of elapsed time
- Assert tick count is approximately 10 (within tolerance, e.g. 8-12)

**Entity lifecycle:**
- Initialise with known seed state (fixed positions, fixed energy values)
- Run for N ticks
- Assert: plants exist, herbivores exist, predator exists (no immediate extinction)
- Assert: at least one entity has moved (herbivores/predators)
- Assert: energy values have changed

**Ecosystem stability:**
- Run simulation for 500 ticks (~50 seconds of simulation time)
- Assert: at least one of each species still alive (basic stability check)
- Assert: total entity count is within a reasonable range (not zero, not exploding)

**Boundary enforcement:**
- Place an entity at the edge of the plateau
- Run movement logic
- Assert: entity stays within bounds

### 1.3 UI Tests

Create `tests/frontend/feedback.test.ts`:

**Feedback submission:**
- Render the feedback panel
- Enter text into the input
- Submit
- Assert: API call was made with correct payload (mock the API)
- Assert: input clears after submission
- Assert: confirmation message appears with reference number

**Queue display:**
- Mock the API to return a list of feedback items
- Render the queue
- Assert: all items are displayed
- Assert: status badges render correctly (pending, done, rejected)
- Assert: agent notes display for completed items

### 1.4 Rendering Tests

Create `tests/frontend/canvas.test.ts`:

**Canvas initialisation:**
- Assert: canvas element exists and has expected dimensions
- Assert: canvas context is valid

**Entity rendering:**
- Initialise with known entities
- Trigger a render
- Assert: no errors thrown (canvas rendering is hard to assert visually, but we can verify it doesn't crash)

---

## Phase 2: Test Harness — Backend

### 2.1 Test Framework Setup

Install pytest and httpx (for async FastAPI testing).

```bash
cd backend
pip install pytest httpx pytest-asyncio
```

### 2.2 API Tests

Create `tests/backend/test_api.py`:

**POST /api/feedback:**
- Submit valid feedback → assert 200, response contains reference number and status "pending"
- Submit empty content → assert 400 or 422
- Submit very long content → assert handled gracefully (either accepted with truncation or rejected with clear error)

**GET /api/feedback:**
- Create several submissions → assert all returned, newest first
- Filter by status → assert only matching items returned

**GET /api/feedback/{reference}:**
- Create a submission → retrieve by reference → assert correct item returned
- Request non-existent reference → assert 404

**Reference number generation:**
- Create multiple submissions → assert references are sequential (LW-001, LW-002, etc.)
- Assert references are unique

### 2.3 Database Tests

Create `tests/backend/test_db.py`:

**Schema integrity:**
- Assert all expected columns exist on the feedback table
- Assert status field only accepts valid values (pending, in_progress, done, rejected)

**Data persistence:**
- Create a submission → close and reopen the database → assert submission still exists

Use a temporary SQLite database for each test run (not the production database).

---

## Phase 3: Deterministic Checks

### 3.1 Frontend Linting

Install and configure ESLint with TypeScript support.

```bash
cd frontend
npm install --save-dev eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin
```

Create a sensible `.eslintrc` — strict enough to catch real issues, not so strict that agent-generated code constantly fails on style:
- No unused variables
- No implicit any
- No unreachable code
- Consistent return types

### 3.2 Backend Linting

Install Ruff (fast, modern Python linter).

```bash
pip install ruff
```

Configure `ruff.toml` in the backend directory:
- Standard rules for unused imports, undefined variables, basic style
- Line length 120 (generous enough for generated code)

### 3.3 Type Checking

**Frontend:** TypeScript compilation (`tsc --noEmit`) — already available via the existing setup.

**Backend:** Optional for now. Add mypy later if type errors become a problem.

---

## Phase 4: CI/CD Pipeline

### 4.1 Pipeline Script

Create `scripts/pipeline.sh` at the repo root. This is the single script that runs the full pipeline — used by both humans and (later) agents.

```
#!/bin/bash
set -e  # Exit on any failure

echo "=== Step 1: Frontend Lint ==="
cd frontend && npx eslint src/ && cd ..

echo "=== Step 2: TypeScript Check ==="
cd frontend && npx tsc --noEmit && cd ..

echo "=== Step 3: Backend Lint ==="
cd backend && ruff check . && cd ..

echo "=== Step 4: Frontend Tests ==="
cd frontend && npx vitest run && cd ..

echo "=== Step 5: Backend Tests ==="
cd backend && python -m pytest tests/ && cd ..

echo "=== Step 6: Build Frontend ==="
cd frontend && npm run build && cd ..

echo "=== All checks passed ==="
```

The script exits on the first failure (`set -e`). Each step has a clear label for debugging.

### 4.2 Deployment Script

Update or create `scripts/deploy.sh`:

```
#!/bin/bash
set -e

echo "=== Running pipeline ==="
./scripts/pipeline.sh

echo "=== Deploying ==="
# Copy frontend build to where FastAPI serves it
cp -r frontend/dist backend/static/

# Restart the backend service
# (method depends on how we're running it — systemd, pm2, or simple process restart)
echo "=== Restarting server ==="
# TBD: restart mechanism

echo "=== Deployment complete ==="
```

### 4.3 Git Hooks (Optional but Recommended)

Install a pre-push hook that runs `scripts/pipeline.sh`. This prevents broken code from reaching main, whether pushed by a human or an agent.

```bash
# .git/hooks/pre-push
#!/bin/bash
./scripts/pipeline.sh
```

---

## Phase 5: Simulation Engine Refactor (If Needed)

This phase only applies if the simulation logic is currently tightly coupled to the React component / canvas rendering.

### 5.1 Decouple Simulation from Rendering

The simulation engine (entities, tick logic, energy, movement, eating, reproduction, death) must be testable without a DOM or canvas. If it isn't already separated:

- Extract the simulation into its own module (e.g. `frontend/src/simulation/engine.ts`)
- The engine exposes: `initialise(config)`, `tick(deltaTime)`, `getEntities()`
- The React component calls the engine and renders the results
- Tests import the engine directly without needing React or a canvas

This refactor is critical — without it, the simulation tests in Phase 1 can't run.

### 5.2 Configuration File

If not already in place, extract simulation parameters into a config file (e.g. `frontend/src/simulation/config.ts`):

```typescript
export const SIMULATION_CONFIG = {
  TICK_RATE: 10,              // ticks per second
  INITIAL_PLANTS: 30,
  INITIAL_HERBIVORES: 15,
  INITIAL_PREDATORS: 5,
  PLANT_REPRODUCTION_RATE: 0.2,  // per second
  ENERGY_DRAIN_RATE: 1,          // per second while moving
  EATING_ENERGY_GAIN: 30,
  REPRODUCTION_THRESHOLD: 70,
  REPRODUCTION_COST: 40,
  WORLD_WIDTH: 800,
  WORLD_HEIGHT: 600,
};
```

This makes tuning easy for both humans and agents.

---

## Phase 6: Validation

### 6.1 Pipeline Validation Checklist

- [ ] `scripts/pipeline.sh` runs end to end on a clean checkout
- [ ] A linting error causes the pipeline to fail and stop
- [ ] A failing test causes the pipeline to fail and stop
- [ ] A TypeScript error causes the pipeline to fail and stop
- [ ] `scripts/deploy.sh` runs the pipeline then deploys successfully
- [ ] After deployment, the app loads and functions correctly
- [ ] The tick rate bug is caught by the new simulation tests (verify by temporarily reintroducing the bug)

### 6.2 Known Gaps (Intentional)

Not in scope for this phase:
- No automated triggering (cron, webhook, etc.) — that comes with the agent framework
- No branch management automation — agents will create branches later
- No Lighthouse or bundle size tracking yet — that's a month 2 observability task
- No Git hooks enforced for agents — they'll push to feature branches that go through the pipeline before merge

---

## Notes for Claude Code

- Phase 5 (simulation refactor) may need to happen before Phase 1 tests can be written — assess the current code structure first and reorder if needed
- Keep tests simple and readable — agents will be reading and potentially modifying these later
- Use descriptive test names that explain what's being validated (e.g. `test_simulation_ticks_at_expected_rate`)
- The pipeline script should work identically on both the Windows development machine and the macOS production machine
- Commit atomically: test framework setup, then simulation tests, then API tests, then linting, then pipeline scripts, then deployment scripts
- Run the full pipeline at the end to verify everything works together
