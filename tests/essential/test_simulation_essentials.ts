// ESSENTIAL TESTS - Human-maintained only
// These tests validate contract.md invariants
// Agents must not modify these files
//
// Coverage notes:
//   - "Tick rate" — ALREADY TESTED in tests/frontend/simulation.test.ts (Tick rate
//     suite). Skipped here to avoid duplication.
//   - "All three species at initialisation" — ALREADY TESTED in
//     tests/frontend/simulation.test.ts (Entity lifecycle > "all three species
//     survive after 50 ticks"). Skipped here.
//   - "Entities stay within plateau bounds after 100 ticks" — NEW. The existing
//     boundary tests (simulation.test.ts) run 20 ticks from artificially
//     edge-positioned entities. This test runs 100 ticks from the default seed
//     and verifies every entity stays in bounds — a broader regression guard.
//   - "Ecosystem doesn't collapse within 500 ticks" — ALREADY TESTED in
//     tests/frontend/simulation.test.ts (Ecosystem stability > "at least one of
//     each species survives after 500 ticks"). Skipped here.

import { describe, it, expect } from "vitest";
import { Simulation } from "../../frontend/src/simulation/simulation";
import {
  WORLD_WIDTH,
  WORLD_HEIGHT,
  PLATEAU_MARGIN,
} from "../../frontend/src/simulation/constants";

describe("Simulation essentials", () => {
  it("all entities stay within plateau bounds after 100 ticks", () => {
    const sim = new Simulation();

    for (let i = 0; i < 100; i++) {
      sim.tick();
    }

    for (const e of sim.entities) {
      expect(e.x).toBeGreaterThanOrEqual(PLATEAU_MARGIN);
      expect(e.x).toBeLessThanOrEqual(WORLD_WIDTH - PLATEAU_MARGIN);
      expect(e.y).toBeGreaterThanOrEqual(PLATEAU_MARGIN);
      expect(e.y).toBeLessThanOrEqual(WORLD_HEIGHT - PLATEAU_MARGIN);
    }
  });
});
