import type { Entity } from "./types";
import { Species } from "./types";
import {
  WORLD_WIDTH,
  WORLD_HEIGHT,
  MAX_ENERGY,
  PLATEAU_MARGIN,
  EATING_ENERGY_GAIN,
  REPRODUCTION_THRESHOLD,
  REPRODUCTION_COST,
  PLANT_ENERGY_REGEN,
  PLANT_ENERGY_DRAIN,
  PLANT_REPRODUCE_CHANCE,
  PLANT_SPAWN_RADIUS,
  PLANT_MAX_DENSITY_RADIUS,
  PLANT_MAX_NEIGHBOURS,
  HERBIVORE_SPEED,
  HERBIVORE_ENERGY_DRAIN,
  HERBIVORE_SENSE_RADIUS,
  HERBIVORE_EAT_RADIUS,
  HERBIVORE_REPRODUCE_CHANCE,
  HERBIVORE_WANDER_CHANGE,
  PREDATOR_SPEED,
  PREDATOR_ENERGY_DRAIN,
  PREDATOR_SENSE_RADIUS,
  PREDATOR_EAT_RADIUS,
  PREDATOR_REPRODUCE_CHANCE,
  PREDATOR_WANDER_CHANGE,
} from "./constants";

export type IdCounter = { value: number };

function clampToWorld(x: number, y: number): [number, number] {
  return [
    Math.max(PLATEAU_MARGIN, Math.min(WORLD_WIDTH - PLATEAU_MARGIN, x)),
    Math.max(PLATEAU_MARGIN, Math.min(WORLD_HEIGHT - PLATEAU_MARGIN, y)),
  ];
}

/** Move an entity by its speed, clamping to world bounds and bouncing if it
 *  hits an edge. Combines the old clampToWorld + bounceIfAtEdge into a single
 *  step so the entity can't get stuck oscillating at the boundary. */
function moveAndContain(entity: Entity, speed: number): void {
  const minX = PLATEAU_MARGIN;
  const maxX = WORLD_WIDTH - PLATEAU_MARGIN;
  const minY = PLATEAU_MARGIN;
  const maxY = WORLD_HEIGHT - PLATEAU_MARGIN;

  let nx = entity.x + Math.cos(entity.direction) * speed;
  let ny = entity.y + Math.sin(entity.direction) * speed;

  let bounced = false;
  if (nx <= minX || nx >= maxX) {
    // Reflect horizontal component of direction
    entity.direction = Math.PI - entity.direction + (Math.random() - 0.5) * 0.4;
    nx = Math.max(minX, Math.min(maxX, nx));
    bounced = true;
  }
  if (ny <= minY || ny >= maxY) {
    // Reflect vertical component of direction
    entity.direction = -entity.direction + (Math.random() - 0.5) * 0.4;
    ny = Math.max(minY, Math.min(maxY, ny));
    bounced = true;
  }

  if (bounced) {
    // Normalise direction to [-PI, PI]
    entity.direction = Math.atan2(
      Math.sin(entity.direction),
      Math.cos(entity.direction),
    );
  }

  entity.x = nx;
  entity.y = ny;
}

function randomInWorld(): [number, number] {
  return [
    PLATEAU_MARGIN + Math.random() * (WORLD_WIDTH - 2 * PLATEAU_MARGIN),
    PLATEAU_MARGIN + Math.random() * (WORLD_HEIGHT - 2 * PLATEAU_MARGIN),
  ];
}

function distance(a: Entity, b: Entity): number {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.sqrt(dx * dx + dy * dy);
}

function angleToward(from: Entity, to: Entity): number {
  return Math.atan2(to.y - from.y, to.x - from.x);
}

function findNearest(
  entity: Entity,
  candidates: Entity[],
  maxRadius: number
): Entity | null {
  let best: Entity | null = null;
  let bestDist = maxRadius;
  for (const c of candidates) {
    const d = distance(entity, c);
    if (d < bestDist) {
      bestDist = d;
      best = c;
    }
  }
  return best;
}

export function createEntity(
  species: Species,
  ids: IdCounter,
  x?: number,
  y?: number,
  energy?: number
): Entity {
  const [rx, ry] = x !== undefined && y !== undefined ? [x, y] : randomInWorld();
  return {
    id: ids.value++,
    species,
    x: rx,
    y: ry,
    energy: energy ?? MAX_ENERGY * 0.6,
    direction: Math.random() * Math.PI * 2,
  };
}

// --- Plant update ---

export function updatePlant(
  plant: Entity,
  allPlants: Entity[],
  newEntities: Entity[],
  ids: IdCounter
): boolean {
  // Photosynthesis
  plant.energy = Math.min(MAX_ENERGY, plant.energy + PLANT_ENERGY_REGEN);
  // Passive drain
  plant.energy -= PLANT_ENERGY_DRAIN;

  if (plant.energy <= 0) return false; // dead

  // Reproduction
  if (
    plant.energy >= REPRODUCTION_THRESHOLD &&
    Math.random() < PLANT_REPRODUCE_CHANCE
  ) {
    // Density check: count neighbours
    let neighbours = 0;
    for (const other of allPlants) {
      if (other.id !== plant.id && distance(plant, other) < PLANT_MAX_DENSITY_RADIUS) {
        neighbours++;
      }
    }
    if (neighbours < PLANT_MAX_NEIGHBOURS) {
      const angle = Math.random() * Math.PI * 2;
      const dist = Math.random() * PLANT_SPAWN_RADIUS;
      const [nx, ny] = clampToWorld(
        plant.x + Math.cos(angle) * dist,
        plant.y + Math.sin(angle) * dist
      );
      plant.energy -= REPRODUCTION_COST;
      newEntities.push(createEntity(Species.Plant, ids, nx, ny, REPRODUCTION_COST * 0.5));
    }
  }

  return true; // alive
}

// --- Herbivore update ---

export function updateHerbivore(
  herb: Entity,
  plants: Entity[],
  newEntities: Entity[],
  ids: IdCounter
): boolean {
  // Try to find food
  const target = findNearest(herb, plants, HERBIVORE_SENSE_RADIUS);

  if (target) {
    herb.direction = angleToward(herb, target);

    if (distance(herb, target) < HERBIVORE_EAT_RADIUS) {
      // Graze: drain energy from plant rather than instant kill
      const drained = Math.min(EATING_ENERGY_GAIN, target.energy);
      herb.energy = Math.min(MAX_ENERGY, herb.energy + drained);
      target.energy -= drained;
    }
  } else if (Math.random() < HERBIVORE_WANDER_CHANGE) {
    herb.direction += (Math.random() - 0.5) * Math.PI * 0.5;
  }

  // Move (handles boundary bouncing)
  moveAndContain(herb, HERBIVORE_SPEED);

  // Energy drain
  herb.energy -= HERBIVORE_ENERGY_DRAIN;

  if (herb.energy <= 0) return false; // dead

  // Reproduction
  if (
    herb.energy >= REPRODUCTION_THRESHOLD &&
    Math.random() < HERBIVORE_REPRODUCE_CHANCE
  ) {
    herb.energy -= REPRODUCTION_COST;
    const angle = Math.random() * Math.PI * 2;
    const [sx, sy] = clampToWorld(
      herb.x + Math.cos(angle) * 20,
      herb.y + Math.sin(angle) * 20
    );
    newEntities.push(createEntity(Species.Herbivore, ids, sx, sy, REPRODUCTION_COST * 0.5));
  }

  return true; // alive
}

// --- Predator update ---

export function updatePredator(
  pred: Entity,
  herbivores: Entity[],
  newEntities: Entity[],
  ids: IdCounter
): boolean {
  // Try to find prey
  const target = findNearest(pred, herbivores, PREDATOR_SENSE_RADIUS);

  if (target) {
    pred.direction = angleToward(pred, target);

    if (distance(pred, target) < PREDATOR_EAT_RADIUS) {
      pred.energy = Math.min(MAX_ENERGY, pred.energy + EATING_ENERGY_GAIN);
      target.energy = 0; // kill the herbivore
    }
  } else if (Math.random() < PREDATOR_WANDER_CHANGE) {
    pred.direction += (Math.random() - 0.5) * Math.PI * 0.5;
  }

  // Move (handles boundary bouncing)
  moveAndContain(pred, PREDATOR_SPEED);

  // Energy drain
  pred.energy -= PREDATOR_ENERGY_DRAIN;

  if (pred.energy <= 0) return false; // dead

  // Reproduction
  if (
    pred.energy >= REPRODUCTION_THRESHOLD &&
    Math.random() < PREDATOR_REPRODUCE_CHANCE
  ) {
    pred.energy -= REPRODUCTION_COST;
    const angle = Math.random() * Math.PI * 2;
    const [sx, sy] = clampToWorld(
      pred.x + Math.cos(angle) * 25,
      pred.y + Math.sin(angle) * 25
    );
    newEntities.push(createEntity(Species.Predator, ids, sx, sy, REPRODUCTION_COST * 0.5));
  }

  return true; // alive
}

