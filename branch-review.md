# Comparative Review: Week 2 Implementation Branches

Three branches each implement `week-2-implementation-plan.md` independently. This review compares them across code quality, architecture extensibility, testability, and ecosystem stability.

| | **Branch A** | **Branch B** | **Branch C** |
|---|---|---|---|
| **Branch** | `build-ecosystem-simulator-9sKeX` | `setup-monorepo-scaffolding-Gkw8T` | `week-2-implementation-acteH` |
| **Branch** | `One-shot` | `Claude plans` | `Claude Code plans` |
| **Commits** | 6 | 6 | 5 |
| **Files** | 28 (~4,794 lines) | 38 (~5,003 lines) | 32 (~4,930 lines) |
| **Stack** | Vite + React/TS, FastAPI + SQLite | Vite + React/TS, FastAPI + SQLite | Vite + React/TS, FastAPI + SQLite |

All three share the same fundamental stack and monorepo layout. The differences lie in simulation design, rendering strategy, and engineering rigor.

---

## 1. Code Quality

### Branch A — Strongest TypeScript, weakest component hygiene

- **Types:** Uses `as const` + mapped type for `Species` — the most idiomatic TypeScript pattern of the three. Strict mode enabled, zero `any` usage. However, `Entity` is a flat bag for all species (no discriminated union), so the type system doesn't prevent nonsensical operations like moving a plant.
- **Naming:** Clear, descriptive function names (`findNearest`, `moveToward`, `constrainToBounds`). Minor inconsistency: `herb` vs `pred` vs full `plant`.
- **Structure:** Clean barrel exports via `simulation/index.ts`. Simulation logic split into `types.ts`, `config.ts`, `engine.ts`, `renderer.ts` — each with a single responsibility.
- **Major weakness:** `FeedbackPanel.tsx` is 261 lines with extensive inline `style` objects (~70 lines of style declarations). Mixes presentation and logic heavily. The component handles fetching, form state, polling, and rendering all in one.
- **Backend:** Modern SQLAlchemy 2.0 with `Mapped` annotations, Pydantic v2 with `from_attributes`. Proper async generators for DB sessions but missing `try/finally` with rollback.
- **Error handling:** Silent `catch` blocks in the frontend (`catch { // Silently fail }`). Backend returns proper HTTP status codes but the reference generator has a race condition.

### Branch B — Best file organization, most thorough scaffolding

- **Types:** `Entity` interface uses `species: Species` as a discriminant. Carries a `direction` field (noted as "ignored for plants" via JSDoc). The flat interface is acknowledged rather than hidden.
- **Naming:** Consistent and descriptive. Constants are well-organized by category with clear in-line comments.
- **Structure:** The most files (38) — includes `DEPLOYMENT.md`, `CONTRIBUTORS.md`, `tests/` directories with `.gitkeep` files, and a `pipeline/` placeholder. The most faithful to the monorepo spec in the plan.
- **Strength:** CSS is properly extracted into `.css` files with BEM-like naming. `FeedbackPanel.css` implements the naturalist aesthetic with proper class separation. This is the only branch that fully separates styles from component logic.
- **Backend:** Same quality as Branch A (SQLAlchemy 2.0, Pydantic v2). Router is cleanly factored into `router_feedback.py`. Missing `max_length` on feedback content.
- **Error handling:** `catch` blocks in `loadItems` are intentionally silent (documented with comments). Backend reference generation has the same race condition as the others.
- **Weakness:** A hardcoded magic number (`0.25`) in `simulation.ts` for plant energy at the cap, contradicting the constant `PLANT_ENERGY_REGEN = 0.5` in `constants.ts` — a clear copy-paste/tuning error that introduces a real bug (see Ecosystem Stability).

### Branch C — Cleanest config, weakest mutation discipline

- **Types:** `Species` is a simple string union type (`"plant" | "herbivore" | "predator"`). `Entity` includes an `alive: boolean` field which leaks implementation detail (it's only used as a mid-tick deletion flag, never survives between ticks).
- **Config:** The best configuration file of the three. All parameters centralized in `config.ts` with `as const` assertions and JSDoc comments on each parameter. Clean per-species config blocks (`PLANT`, `HERBIVORE`, `PREDATOR`). **However**, reproduction probabilities are hardcoded in `engine.ts` (`Math.random() < 0.02`), breaking the "single source of truth" promise of the config file.
- **Structure:** Clean separation, but fewer files than Branch B — no placeholder directories for tests/pipeline.
- **Major weakness:** The `tick()` function **mutates entities in place** (`p.energy -= ...`, `h.x = nx`, `target.alive = false`) despite the function signature implying it returns a new state. This is the most architecturally concerning pattern of all three branches — it makes the state unpredictable if anything holds a reference to the previous tick's data.
- **CSS:** Well-organized with custom properties (CSS variables) for the color palette. 318 lines of clean, responsive CSS with section comments. Responsive breakpoint at 820px.
- **Backend:** Same patterns as the others. Database tables created at module import time rather than via a lifespan handler (would break with a real database). Same reference race condition.

### Code Quality Verdict

**Branch B > Branch A > Branch C**

Branch B has the best overall hygiene: proper CSS extraction, thorough scaffolding, and the most maintainable file organization. Branch A has the strongest TypeScript usage but suffers from inline styles. Branch C has the best config file but the in-place mutation pattern is a significant code smell.

---

## 2. Architecture Extensibility

### Adding a new species (e.g., "fish")

| Step | Branch A | Branch B | Branch C |
|---|---|---|---|
| Define species type | Add to `Species` const | Add to `Species` enum | Add to `Species` union |
| Add parameters | Add `fishSpeed`, `fishEnergyDrain`, etc. as **individual named fields** in `SimulationConfig` | Add constants in `constants.ts` | Add a `FISH` config block in `config.ts` |
| Simulation logic | Add block in monolithic `tick()` | Add `updateFish()` function + section in `tick()` | Add block in `tick()` |
| Rendering | Add drawing function in `renderer.ts` | Add `drawFish()` in canvas component | Add drawing function in `renderer.ts` |
| UI/legend updates | Update `App.tsx` legend | Update population counter + legend | Update legend |
| **Total touch points** | **~5 files, requires type changes** | **~9 files** | **~5 files** |

**Branch A's config doesn't scale.** Per-species parameters are individually named fields (`herbivoreSpeed`, `predatorSpeed`). Adding a species means adding type definitions and 6+ new named fields. The config should be a `Record<Species, SpeciesConfig>` map.

**Branch B has the most touch points (9)** but each one is small and follows an obvious pattern. The separation of `updateHerbivore`/`updatePredator` into individual functions makes the pattern clear. The duplication between these functions is a code smell, but it makes the "how to add a species" recipe obvious.

**Branch C has the best config structure** (`PLANT`, `HERBIVORE`, `PREDATOR` as separate blocks), making it the most natural to extend with a new `FISH` block. But the hardcoded reproduction probabilities in `engine.ts` mean some parameters are in config and some are buried in logic — a developer adding fish could easily miss this.

### Adding terrain features

All three branches treat the water source as purely decorative — it is rendered but has no effect on entity behavior. None has a terrain abstraction or spatial query system. Adding terrain interactions (e.g., "plants grow faster near water") would require modifying `tick()` directly in all three.

**Branch C** has the cleanest separation here because its `config.ts` includes `WATER_SOURCE` as a named config block, and the engine already checks `isInWater()` to block entity spawning/movement. Extending this to affect energy rates would be the most natural.

### Adding an event/observation system

None of the branches has an event bus. Deaths, births, and eating events are implicit (entities disappear, new ones appear). Adding a "naturalist's log" or population graph would require instrumenting the tick function in all three.

**Branch B's `Simulation` class** is the best positioned for this — it already tracks `populationCounts` and has a `respawnIfExtinct()` method, showing awareness of the need for meta-level observation of the ecosystem.

### Extensibility Verdict

**Branch C ≈ Branch B > Branch A**

Branch C has the best config structure for data-driven species addition. Branch B has the best runtime awareness (population tracking, respawn mechanism). Branch A's individually-named config fields are the least scalable pattern.

---

## 3. Testability

### Current test coverage: All three branches have **zero tests**.

None configures a test runner (no vitest, jest, or pytest in dependencies). Branch B at least creates `tests/` directories with `.gitkeep` — a signal that tests are planned.

### How testable is the simulation engine?

| Aspect | Branch A | Branch B | Branch C |
|---|---|---|---|
| **Purity of tick()** | Pure function `(state, config) => state` | Class method, mutates internal `entities` array | Returns new state but **mutates entities in place** |
| **Random number injection** | Uses `Math.random()` directly — must mock globally | Uses `Math.random()` directly — must mock globally | Uses `Math.random()` directly — must mock globally |
| **ID generation** | Counter in `SimulationState` (per-instance) | **Global mutable `let nextId = 1`** at module level | Counter in state (per-instance) |
| **State isolation** | Full — each tick returns a new state object | Partial — `Simulation` class holds mutable state | **Broken** — mutations leak across tick boundaries |

**Branch A is the most testable.** Its `tick()` is a genuine pure function: `(SimulationState, SimulationConfig) => SimulationState`. You can construct a specific state (e.g., one herbivore next to one plant), run a tick, and assert on the result. The ID counter is part of the state object, so tests are isolated.

**Branch B is moderately testable.** The `Simulation` class is instantiable, but the global `nextId` counter is shared across instances. Two test fixtures using different `Simulation` instances would share ID space. The `updatePlant`/`updateHerbivore`/`updatePredator` functions return boolean alive/dead signals, which is clean for unit testing individual behaviors.

**Branch C is the least testable.** The in-place mutation of entities means you cannot snapshot state before a tick and compare it to state after — the "before" snapshot has been mutated. Testing would require deep-cloning state before each tick, which is doable but fragile. The hardcoded reproduction probabilities make tests non-deterministic even beyond `Math.random()`.

### Backend testability

All three backends are equally testable — FastAPI's `TestClient` with an overridden `get_db` dependency pointing to an in-memory SQLite database would work for all of them. The Pydantic schemas provide automatic validation testing.

### React component testability

All three use Canvas for the ecosystem, which is inherently hard to unit test. Branch A stores simulation state in refs, making inspection difficult. Branch C uses a custom hook (`useSimulation`) which could be tested with `renderHook` from React Testing Library. Branch B's `EcosystemCanvas` owns the `Simulation` instance in a ref.

For the feedback panel, Branch B's `FeedbackPanel` is the most testable because it uses a proper CSS file (no inline styles to assert against) and has the cleanest separation between the `FeedbackEntry` sub-component and the parent.

### Testability Verdict

**Branch A > Branch B > Branch C**

Branch A's pure-function simulation engine is the gold standard for testability. Branch B is reasonable but hampered by global mutable state. Branch C's in-place mutation pattern fundamentally undermines test isolation.

---

## 4. Stability of Simulated Ecosystem

This is the most critical dimension — the plan says the goal is "visibly alive, not perfectly balanced."

### Energy balance comparison

| Parameter | Branch A | Branch B | Branch C |
|---|---|---|---|
| **Plant net energy/tick** | +0.06 (+0.08 gain, -0.02 drain) | +0.45 (+0.5 gain, -0.05 drain) | +0.12 (+0.15 gain, -0.03 drain) |
| **Herbivore drain/tick** | -0.1 (1.0/s) | -0.08 (0.8/s) | -0.1 (1.0/s) |
| **Predator drain/tick** | -0.1 (1.0/s) | -0.2 (2.0/s) | -0.15 (1.5/s) |
| **Energy from eating** | +30 | +20 (grazing) | +30 |
| **Reproduction threshold** | 70 | 70 | 70 |
| **Reproduction cost** | 40 | 40 | 40 |
| **Plant density cap** | Yes (per 100x100 area) | Yes (global cap of 120) | Yes (global cap of 120) |
| **Animal population cap** | **No** | **No** | **No** |
| **Reproduction cooldown (animals)** | **None** | Probabilistic (~4.5%/tick) | Probabilistic (2%/1.5% per tick) |

### Critical stability issues by branch

**Branch A — Population explosion via uncapped reproduction**

The most severe issue across all branches. Herbivores and predators check `if (energy > 70)` **every tick** with no cooldown. After eating (+30 energy), a herbivore at 65 energy jumps to 95, immediately reproduces (drops to 55), and if it eats again quickly, reproduces again. This creates exponential growth → resource exhaustion → mass starvation → possible extinction. There is **no respawn mechanism** if a species goes extinct, so collapse is permanent.

Predicted outcome: **Boom-bust cycles ending in permanent extinction within 2-5 minutes.**

**Branch B — Immortal plants at cap (bug), but best safety nets**

The `simulation.ts` plant-cap code applies a hardcoded `+0.25` energy/tick with no drain when the plant count reaches 120. These plants **never lose energy and never die**, creating an immortal food floor. Herbivores will always have food, preventing complete ecosystem collapse — but this is a bug, not a feature. The energy value contradicts `PLANT_ENERGY_REGEN = 0.5` in constants.

Counterbalancing strengths: Branch B has the **best stability mechanisms**:
- **Respawn on extinction:** If any species hits zero, it respawns a small group (9 plants, 3 herbivores, 3 predators). This prevents permanent collapse.
- **Grazing mechanic:** Herbivores drain plant energy partially (`Math.min(EATING_ENERGY_GAIN, target.energy)`) rather than instant-killing. Multiple herbivores can feed from one plant. This smooths the predator-prey dynamics significantly.
- **Bounce-at-edge:** Adds randomness to direction when entities hit boundaries, distributing them across the map.

Predicted outcome: **Stable but slightly artificial.** The immortal-plant bug acts as an accidental stabilizer. With the bug fixed, the respawn mechanism would still prevent permanent collapse, making this the most resilient ecosystem.

**Branch C — No catch-up cap, no population ceiling**

The `useSimulation` hook has an unbounded catch-up loop. If the browser tab is backgrounded for even 30 seconds, returning to it will trigger 300+ synchronous ticks in a single frame, likely freezing the browser for seconds. During this burst, population dynamics run unchecked — a small imbalance becomes a huge one.

The reproduction probabilities (2% for herbivores, 1.5% for predators per tick above threshold) are more conservative than Branch A's every-tick reproduction, but there are **no population caps for animals**. With abundant plants, herbivore counts can grow to hundreds, causing O(n^2) performance degradation in nearest-neighbor searches.

Predicted outcome: **Reasonable short-term dynamics with periodic browser freezes and gradual performance degradation.**

### Tick-rate decoupling

| | Branch A | Branch B | Branch C |
|---|---|---|---|
| **Render loop** | `requestAnimationFrame` | `requestAnimationFrame` | `requestAnimationFrame` |
| **Tick loop** | Fixed-rate with catch-up, **capped at 3 ticks/frame** | `setInterval` at `TICK_INTERVAL` | Fixed-timestep accumulator, **no catch-up cap** |
| **Background tab safety** | Safe (cap of 3) | Mostly safe (setInterval is throttled by browsers) | **Unsafe** (unbounded catch-up) |
| **Parameters** | Per-tick (changing tickRate changes behavior) | Per-tick (same coupling) | Per-tick (same coupling) |

Branch A's catch-up cap of 3 is the best approach. Branch B's `setInterval` is adequate because browsers throttle intervals in background tabs. Branch C's unbounded catch-up is a genuine stability risk.

### Ecosystem Stability Verdict

**Branch B > Branch C > Branch A**

Branch B is the most stable despite the plant-cap bug — its respawn mechanism, grazing mechanic, and probabilistic reproduction produce the most resilient ecosystem. Branch C has reasonable parameters but the unbounded catch-up loop is a real usability issue. Branch A's every-tick reproduction with no cooldown and no extinction recovery makes it the most fragile.

---

## Overall Summary

| Dimension | 1st | 2nd | 3rd |
|---|---|---|---|
| **Code Quality** | Branch B | Branch A | Branch C |
| **Extensibility** | Branch C ≈ B | — | Branch A |
| **Testability** | Branch A | Branch B | Branch C |
| **Ecosystem Stability** | Branch B | Branch C | Branch A |

### Branch A (`build-ecosystem-simulator`)
**Best at:** Pure-function architecture, TypeScript rigor, testability.
**Worst at:** Ecosystem stability (no reproduction cooldown, no extinction recovery). Inline styles.
**If you pick this branch:** Add reproduction cooldowns immediately, add a respawn mechanism, extract inline styles.

### Branch B (`setup-monorepo-scaffolding`)
**Best at:** Overall code hygiene, ecosystem stability, file organization, visual design separation.
**Worst at:** Slightly over-scaffolded (38 files). Has the plant-cap immortality bug. Global mutable ID counter.
**If you pick this branch:** Fix the hardcoded `0.25` plant energy at cap, move `nextId` into the Simulation class, add DPI-awareness to the canvas.

### Branch C (`week-2-implementation`)
**Best at:** Config structure, responsive CSS.
**Worst at:** In-place entity mutation (breaks immutability contract), unbounded tick catch-up (browser freeze risk), hardcoded reproduction probabilities.
**If you pick this branch:** Add a catch-up cap immediately, stop mutating entities in place, move reproduction probabilities to config.

### Recommendation

**Branch B is the strongest foundation for week 3 and beyond.** It has the fewest critical bugs (the plant-cap issue is a one-line fix), the best stability mechanisms (respawn + grazing), the cleanest file organization, and proper CSS separation. Its moderate testability weakness (global `nextId`) is easily fixed by moving the counter into the `Simulation` class.

If testability is the top priority (e.g., for the agent pipeline in week 3 that will modify the simulation), **Branch A's pure-function engine could be grafted onto Branch B's scaffolding** — taking A's `engine.ts` architecture with B's rendering, stability mechanisms, and project organization.
