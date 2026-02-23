import { describe, it, expect } from "vitest";
import { Simulation } from "../../frontend/src/simulation/simulation";
import { Species } from "../../frontend/src/simulation/types";
import type { Entity } from "../../frontend/src/simulation/types";
import {
  TICK_RATE,
  TICK_INTERVAL,
  WORLD_WIDTH,
  WORLD_HEIGHT,
  PLATEAU_MARGIN,
  INITIAL_PLANTS,
  INITIAL_HERBIVORES,
  INITIAL_PREDATORS,
  PLANT_CAP,
  HERBIVORE_CAP,
  PREDATOR_CAP,
} from "../../frontend/src/simulation/constants";
import { createEntity } from "../../frontend/src/simulation/entities";
import type { IdCounter } from "../../frontend/src/simulation/entities";

// ---------------------------------------------------------------------------
// Tick Rate
// ---------------------------------------------------------------------------

describe("Tick rate", () => {
  it("produces approximately 10 ticks per simulated second of elapsed time", () => {
    // Replicate the accumulator pattern used by EcosystemCanvas to convert
    // wall-clock milliseconds into discrete ticks.
    const sim = new Simulation();
    const ONE_SECOND_MS = 1000;
    const FRAME_MS = 16; // ~60 fps
    const MAX_CATCHUP_TICKS = 10;

    let accumulator = 0;
    let totalTicks = 0;

    // Simulate frames for exactly 1 second of wall-clock time
    for (let elapsed = 0; elapsed < ONE_SECOND_MS; elapsed += FRAME_MS) {
      accumulator += FRAME_MS;
      const ticks = Math.min(
        Math.floor(accumulator / TICK_INTERVAL),
        MAX_CATCHUP_TICKS,
      );
      accumulator -= ticks * TICK_INTERVAL;
      totalTicks += ticks;

      for (let i = 0; i < ticks; i++) {
        sim.tick();
      }
    }

    // TICK_RATE is 10; allow tolerance 8-12
    expect(totalTicks).toBeGreaterThanOrEqual(8);
    expect(totalTicks).toBeLessThanOrEqual(12);
  });
});

// ---------------------------------------------------------------------------
// Entity Lifecycle
// ---------------------------------------------------------------------------

describe("Entity lifecycle", () => {
  it("all three species survive after 50 ticks with default seeding", () => {
    const sim = new Simulation();

    // Verify initial populations are what we expect
    const initial = sim.populationCounts;
    expect(initial.plants).toBe(INITIAL_PLANTS);
    expect(initial.herbivores).toBe(INITIAL_HERBIVORES);
    expect(initial.predators).toBe(INITIAL_PREDATORS);

    for (let i = 0; i < 50; i++) {
      sim.tick();
    }

    const counts = sim.populationCounts;
    expect(counts.plants).toBeGreaterThan(0);
    expect(counts.herbivores).toBeGreaterThan(0);
    expect(counts.predators).toBeGreaterThan(0);
  });

  it("at least one herbivore or predator has moved after 10 ticks", () => {
    const sim = new Simulation();

    // Snapshot starting positions of all mobile entities
    const startPositions = new Map<number, { x: number; y: number }>();
    for (const e of sim.entities) {
      if (e.species !== Species.Plant) {
        startPositions.set(e.id, { x: e.x, y: e.y });
      }
    }

    for (let i = 0; i < 10; i++) {
      sim.tick();
    }

    let anyMoved = false;
    for (const e of sim.entities) {
      const start = startPositions.get(e.id);
      if (start && (e.x !== start.x || e.y !== start.y)) {
        anyMoved = true;
        break;
      }
    }

    expect(anyMoved).toBe(true);
  });

  it("energy values change after running ticks", () => {
    const sim = new Simulation();

    const startEnergies = new Map<number, number>();
    for (const e of sim.entities) {
      startEnergies.set(e.id, e.energy);
    }

    for (let i = 0; i < 10; i++) {
      sim.tick();
    }

    let anyChanged = false;
    for (const e of sim.entities) {
      const start = startEnergies.get(e.id);
      if (start !== undefined && e.energy !== start) {
        anyChanged = true;
        break;
      }
    }

    expect(anyChanged).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Ecosystem Stability
// ---------------------------------------------------------------------------

describe("Ecosystem stability", () => {
  it("at least one of each species survives after 500 ticks", () => {
    const sim = new Simulation();

    for (let i = 0; i < 500; i++) {
      sim.tick();
    }

    const counts = sim.populationCounts;
    expect(counts.plants).toBeGreaterThan(0);
    expect(counts.herbivores).toBeGreaterThan(0);
    expect(counts.predators).toBeGreaterThan(0);
  });

  it("total entity count stays within a reasonable range after 500 ticks", () => {
    const sim = new Simulation();

    for (let i = 0; i < 500; i++) {
      sim.tick();
    }

    const total = sim.entities.length;
    const maxPossible = PLANT_CAP + HERBIVORE_CAP + PREDATOR_CAP;

    // Not zero, not exceeding all caps combined
    expect(total).toBeGreaterThan(0);
    expect(total).toBeLessThanOrEqual(maxPossible);
  });
});

// ---------------------------------------------------------------------------
// Boundary Enforcement
// ---------------------------------------------------------------------------

describe("Boundary enforcement", () => {
  it("entity at the right edge stays within bounds after movement ticks", () => {
    const sim = new Simulation();

    // Place a herbivore at the far right edge, heading rightward
    const edgeEntity = sim.entities.find(
      (e) => e.species === Species.Herbivore,
    )!;
    edgeEntity.x = WORLD_WIDTH - PLATEAU_MARGIN;
    edgeEntity.y = WORLD_HEIGHT / 2;
    edgeEntity.direction = 0; // heading right

    for (let i = 0; i < 20; i++) {
      sim.tick();
    }

    // All surviving entities must be within world bounds
    for (const e of sim.entities) {
      expect(e.x).toBeGreaterThanOrEqual(PLATEAU_MARGIN);
      expect(e.x).toBeLessThanOrEqual(WORLD_WIDTH - PLATEAU_MARGIN);
      expect(e.y).toBeGreaterThanOrEqual(PLATEAU_MARGIN);
      expect(e.y).toBeLessThanOrEqual(WORLD_HEIGHT - PLATEAU_MARGIN);
    }
  });

  it("entity at the top edge stays within bounds after movement ticks", () => {
    const sim = new Simulation();

    const edgeEntity = sim.entities.find(
      (e) => e.species === Species.Predator,
    )!;
    edgeEntity.x = WORLD_WIDTH / 2;
    edgeEntity.y = PLATEAU_MARGIN;
    edgeEntity.direction = -Math.PI / 2; // heading upward

    for (let i = 0; i < 20; i++) {
      sim.tick();
    }

    for (const e of sim.entities) {
      expect(e.x).toBeGreaterThanOrEqual(PLATEAU_MARGIN);
      expect(e.x).toBeLessThanOrEqual(WORLD_WIDTH - PLATEAU_MARGIN);
      expect(e.y).toBeGreaterThanOrEqual(PLATEAU_MARGIN);
      expect(e.y).toBeLessThanOrEqual(WORLD_HEIGHT - PLATEAU_MARGIN);
    }
  });

  it("entity placed exactly at a corner stays within bounds", () => {
    const sim = new Simulation();

    // Push a herbivore to the bottom-left corner heading diagonally outward
    const corner = sim.entities.find(
      (e) => e.species === Species.Herbivore,
    )!;
    corner.x = PLATEAU_MARGIN;
    corner.y = WORLD_HEIGHT - PLATEAU_MARGIN;
    corner.direction = Math.PI * 0.75; // heading down-left

    for (let i = 0; i < 20; i++) {
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
