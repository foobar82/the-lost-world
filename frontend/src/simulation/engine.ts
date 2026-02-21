import {
  WORLD,
  INITIAL_COUNTS,
  ENERGY,
  PLANT,
  HERBIVORE,
  PREDATOR,
  WATER_SOURCE,
} from "./config";
import type { Entity, SimulationState, Species } from "./types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function rand(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

function dist(a: { x: number; y: number }, b: { x: number; y: number }): number {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.sqrt(dx * dx + dy * dy);
}

function clampToWorld(x: number, y: number): [number, number] {
  return [
    Math.max(10, Math.min(WORLD.width - 10, x)),
    Math.max(10, Math.min(WORLD.height - 10, y)),
  ];
}

function isInWater(x: number, y: number): boolean {
  return dist({ x, y }, WATER_SOURCE) < WATER_SOURCE.radius;
}

function randomWorldPosition(): [number, number] {
  let x: number, y: number;
  do {
    x = rand(20, WORLD.width - 20);
    y = rand(20, WORLD.height - 20);
  } while (isInWater(x, y));
  return [x, y];
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

export function createInitialState(): SimulationState {
  const entities: Entity[] = [];
  let nextId = 1;

  const spawn = (species: Species, count: number) => {
    for (let i = 0; i < count; i++) {
      const [x, y] = randomWorldPosition();
      entities.push({
        id: nextId++,
        species,
        x,
        y,
        energy: rand(40, 80),
        alive: true,
      });
    }
  };

  spawn("plant", INITIAL_COUNTS.plants);
  spawn("herbivore", INITIAL_COUNTS.herbivores);
  spawn("predator", INITIAL_COUNTS.predators);

  return { entities, nextId, tickCount: 0 };
}

// ---------------------------------------------------------------------------
// Per-tick update
// ---------------------------------------------------------------------------

export function tick(state: SimulationState): SimulationState {
  const { entities } = state;
  let nextId = state.nextId;
  const newborns: Entity[] = [];

  const alive = (e: Entity) => e.alive;
  const plants = entities.filter((e) => alive(e) && e.species === "plant");
  const herbivores = entities.filter((e) => alive(e) && e.species === "herbivore");
  const predators = entities.filter((e) => alive(e) && e.species === "predator");

  // --- Plants ---
  for (const p of plants) {
    // Photosynthesis
    p.energy = Math.min(ENERGY.max, p.energy + PLANT.photosynthesisRate);
    // Slow decay
    p.energy -= PLANT.decayRate;

    if (p.energy <= 0) {
      p.alive = false;
      continue;
    }

    // Reproduce
    if (
      p.energy >= ENERGY.reproductionThreshold &&
      plants.length + newborns.filter((n) => n.species === "plant").length < PLANT.densityCap &&
      Math.random() < 1 / PLANT.reproductionInterval
    ) {
      p.energy -= ENERGY.reproductionCost;
      let [nx, ny] = [
        p.x + rand(-PLANT.spawnRadius, PLANT.spawnRadius),
        p.y + rand(-PLANT.spawnRadius, PLANT.spawnRadius),
      ];
      [nx, ny] = clampToWorld(nx, ny);
      if (!isInWater(nx, ny)) {
        newborns.push({
          id: nextId++,
          species: "plant",
          x: nx,
          y: ny,
          energy: 30,
          alive: true,
        });
      }
    }
  }

  // --- Herbivores ---
  for (const h of herbivores) {
    h.energy -= HERBIVORE.energyDrain;
    if (h.energy <= 0) {
      h.alive = false;
      continue;
    }

    // Seek nearest plant
    let target: Entity | null = null;
    let bestDist: number = HERBIVORE.senseRadius;
    for (const p of plants) {
      if (!p.alive) continue;
      const d = dist(h, p);
      if (d < bestDist) {
        bestDist = d;
        target = p;
      }
    }

    if (target) {
      // Move toward target
      const d = dist(h, target);
      if (d > HERBIVORE.eatRadius) {
        const ratio = HERBIVORE.speed / d;
        let nx = h.x + (target.x - h.x) * ratio;
        let ny = h.y + (target.y - h.y) * ratio;
        [nx, ny] = clampToWorld(nx, ny);
        if (!isInWater(nx, ny)) {
          h.x = nx;
          h.y = ny;
        }
      } else {
        // Eat
        target.alive = false;
        h.energy = Math.min(ENERGY.max, h.energy + ENERGY.eatingGain);
      }
    } else {
      // Random wander
      const angle = rand(0, Math.PI * 2);
      let nx = h.x + Math.cos(angle) * HERBIVORE.speed;
      let ny = h.y + Math.sin(angle) * HERBIVORE.speed;
      [nx, ny] = clampToWorld(nx, ny);
      if (!isInWater(nx, ny)) {
        h.x = nx;
        h.y = ny;
      }
    }

    // Reproduce
    if (h.energy >= ENERGY.reproductionThreshold && Math.random() < 0.02) {
      h.energy -= ENERGY.reproductionCost;
      let [nx, ny] = [
        h.x + rand(-HERBIVORE.spawnRadius, HERBIVORE.spawnRadius),
        h.y + rand(-HERBIVORE.spawnRadius, HERBIVORE.spawnRadius),
      ];
      [nx, ny] = clampToWorld(nx, ny);
      if (!isInWater(nx, ny)) {
        newborns.push({
          id: nextId++,
          species: "herbivore",
          x: nx,
          y: ny,
          energy: 30,
          alive: true,
        });
      }
    }
  }

  // --- Predators ---
  for (const pr of predators) {
    pr.energy -= PREDATOR.energyDrain;
    if (pr.energy <= 0) {
      pr.alive = false;
      continue;
    }

    // Seek nearest herbivore
    let target: Entity | null = null;
    let bestDist: number = PREDATOR.senseRadius;
    for (const h of herbivores) {
      if (!h.alive) continue;
      const d = dist(pr, h);
      if (d < bestDist) {
        bestDist = d;
        target = h;
      }
    }

    if (target) {
      const d = dist(pr, target);
      if (d > PREDATOR.eatRadius) {
        const ratio = PREDATOR.speed / d;
        let nx = pr.x + (target.x - pr.x) * ratio;
        let ny = pr.y + (target.y - pr.y) * ratio;
        [nx, ny] = clampToWorld(nx, ny);
        if (!isInWater(nx, ny)) {
          pr.x = nx;
          pr.y = ny;
        }
      } else {
        target.alive = false;
        pr.energy = Math.min(ENERGY.max, pr.energy + ENERGY.eatingGain);
      }
    } else {
      const angle = rand(0, Math.PI * 2);
      let nx = pr.x + Math.cos(angle) * PREDATOR.speed;
      let ny = pr.y + Math.sin(angle) * PREDATOR.speed;
      [nx, ny] = clampToWorld(nx, ny);
      if (!isInWater(nx, ny)) {
        pr.x = nx;
        pr.y = ny;
      }
    }

    // Reproduce
    if (pr.energy >= ENERGY.reproductionThreshold && Math.random() < 0.015) {
      pr.energy -= ENERGY.reproductionCost;
      let [nx, ny] = [
        pr.x + rand(-PREDATOR.spawnRadius, PREDATOR.spawnRadius),
        pr.y + rand(-PREDATOR.spawnRadius, PREDATOR.spawnRadius),
      ];
      [nx, ny] = clampToWorld(nx, ny);
      if (!isInWater(nx, ny)) {
        newborns.push({
          id: nextId++,
          species: "predator",
          x: nx,
          y: ny,
          energy: 30,
          alive: true,
        });
      }
    }
  }

  // Merge and cull dead
  const nextEntities = [...entities, ...newborns].filter((e) => e.alive);

  return {
    entities: nextEntities,
    nextId,
    tickCount: state.tickCount + 1,
  };
}
