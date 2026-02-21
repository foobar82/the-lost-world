import { Species } from './types';
import type { Entity, SimulationConfig, SimulationState } from './types';

function randomInRange(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

function distance(a: { x: number; y: number }, b: { x: number; y: number }): number {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.sqrt(dx * dx + dy * dy);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

// Plateau boundary margin — entities stay within this
const BOUNDARY_MARGIN = 20;

export function createInitialState(config: SimulationConfig): SimulationState {
  const entities: Entity[] = [];
  let nextId = 1;

  const minX = BOUNDARY_MARGIN;
  const maxX = config.worldWidth - BOUNDARY_MARGIN;
  const minY = BOUNDARY_MARGIN;
  const maxY = config.worldHeight - BOUNDARY_MARGIN;

  for (let i = 0; i < config.initialPlants; i++) {
    entities.push({
      id: nextId++,
      species: Species.Plant,
      x: randomInRange(minX, maxX),
      y: randomInRange(minY, maxY),
      energy: randomInRange(40, 80),
      age: 0,
    });
  }

  for (let i = 0; i < config.initialHerbivores; i++) {
    entities.push({
      id: nextId++,
      species: Species.Herbivore,
      x: randomInRange(minX, maxX),
      y: randomInRange(minY, maxY),
      energy: randomInRange(50, 80),
      age: 0,
    });
  }

  for (let i = 0; i < config.initialPredators; i++) {
    entities.push({
      id: nextId++,
      species: Species.Predator,
      x: randomInRange(minX, maxX),
      y: randomInRange(minY, maxY),
      energy: randomInRange(50, 80),
      age: 0,
    });
  }

  return { entities, nextId, tickCount: 0 };
}

function findNearest(
  entity: Entity,
  targets: Entity[],
  maxRadius: number
): Entity | null {
  let nearest: Entity | null = null;
  let nearestDist = maxRadius;
  for (const target of targets) {
    const d = distance(entity, target);
    if (d < nearestDist) {
      nearest = target;
      nearestDist = d;
    }
  }
  return nearest;
}

function moveToward(
  entity: Entity,
  target: { x: number; y: number },
  speed: number,
  config: SimulationConfig
) {
  const dx = target.x - entity.x;
  const dy = target.y - entity.y;
  const d = Math.sqrt(dx * dx + dy * dy);
  if (d < speed) {
    entity.x = target.x;
    entity.y = target.y;
  } else {
    entity.x += (dx / d) * speed;
    entity.y += (dy / d) * speed;
  }
  constrainToBounds(entity, config);
}

function moveRandomly(entity: Entity, speed: number, config: SimulationConfig) {
  const angle = Math.random() * Math.PI * 2;
  entity.x += Math.cos(angle) * speed;
  entity.y += Math.sin(angle) * speed;
  constrainToBounds(entity, config);
}

function constrainToBounds(entity: Entity, config: SimulationConfig) {
  entity.x = clamp(entity.x, BOUNDARY_MARGIN, config.worldWidth - BOUNDARY_MARGIN);
  entity.y = clamp(entity.y, BOUNDARY_MARGIN, config.worldHeight - BOUNDARY_MARGIN);
}

function countPlantsNear(x: number, y: number, plants: Entity[]): number {
  let count = 0;
  for (const p of plants) {
    if (Math.abs(p.x - x) < 50 && Math.abs(p.y - y) < 50) {
      count++;
    }
  }
  return count;
}

const EATING_DISTANCE = 12;

export function tick(state: SimulationState, config: SimulationConfig): SimulationState {
  const newEntities: Entity[] = [];
  let nextId = state.nextId;

  const plants = state.entities.filter(e => e.species === Species.Plant);
  const herbivores = state.entities.filter(e => e.species === Species.Herbivore);
  const predators = state.entities.filter(e => e.species === Species.Predator);

  // Track which entities got eaten this tick
  const eaten = new Set<number>();

  // --- Update plants ---
  for (const plant of plants) {
    // Photosynthesis
    plant.energy = Math.min(config.maxEnergy, plant.energy + config.plantPhotosynthesisRate);
    // Drain
    plant.energy -= config.plantEnergyDrain;
    plant.age++;

    if (plant.energy <= 0) continue; // Dies

    // Reproduction
    if (
      plant.age > 0 &&
      plant.age % config.plantReproductionInterval === 0 &&
      plant.energy > config.reproductionThreshold
    ) {
      const nearbyCount = countPlantsNear(plant.x, plant.y, plants);
      if (nearbyCount < config.plantDensityCap) {
        plant.energy -= config.reproductionCost;
        const offsetX = randomInRange(-30, 30);
        const offsetY = randomInRange(-30, 30);
        newEntities.push({
          id: nextId++,
          species: Species.Plant,
          x: clamp(plant.x + offsetX, BOUNDARY_MARGIN, config.worldWidth - BOUNDARY_MARGIN),
          y: clamp(plant.y + offsetY, BOUNDARY_MARGIN, config.worldHeight - BOUNDARY_MARGIN),
          energy: 30,
          age: 0,
        });
      }
    }
  }

  // --- Update herbivores ---
  for (const herb of herbivores) {
    herb.energy -= config.herbivoreEnergyDrain;
    herb.age++;

    if (herb.energy <= 0) continue; // Dies

    // Seek nearest plant
    const availablePlants = plants.filter(p => !eaten.has(p.id) && p.energy > 0);
    const nearestPlant = findNearest(herb, availablePlants, config.herbivoreSenseRadius);

    if (nearestPlant) {
      moveToward(herb, nearestPlant, config.herbivoreSpeed, config);
      if (distance(herb, nearestPlant) < EATING_DISTANCE) {
        herb.energy = Math.min(config.maxEnergy, herb.energy + config.eatingEnergyGain);
        eaten.add(nearestPlant.id);
      }
    } else {
      moveRandomly(herb, config.herbivoreSpeed, config);
    }

    // Reproduction
    if (herb.energy > config.reproductionThreshold) {
      herb.energy -= config.reproductionCost;
      newEntities.push({
        id: nextId++,
        species: Species.Herbivore,
        x: herb.x + randomInRange(-15, 15),
        y: herb.y + randomInRange(-15, 15),
        energy: 30,
        age: 0,
      });
    }
  }

  // --- Update predators ---
  for (const pred of predators) {
    pred.energy -= config.predatorEnergyDrain;
    pred.age++;

    if (pred.energy <= 0) continue; // Dies

    // Seek nearest herbivore
    const availableHerbs = herbivores.filter(h => !eaten.has(h.id) && h.energy > 0);
    const nearestHerb = findNearest(pred, availableHerbs, config.predatorSenseRadius);

    if (nearestHerb) {
      moveToward(pred, nearestHerb, config.predatorSpeed, config);
      if (distance(pred, nearestHerb) < EATING_DISTANCE) {
        pred.energy = Math.min(config.maxEnergy, pred.energy + config.eatingEnergyGain);
        eaten.add(nearestHerb.id);
      }
    } else {
      moveRandomly(pred, config.predatorSpeed, config);
    }

    // Reproduction
    if (pred.energy > config.reproductionThreshold) {
      pred.energy -= config.reproductionCost;
      newEntities.push({
        id: nextId++,
        species: Species.Predator,
        x: pred.x + randomInRange(-15, 15),
        y: pred.y + randomInRange(-15, 15),
        energy: 30,
        age: 0,
      });
    }
  }

  // Collect surviving entities + newborns
  const survivors = state.entities.filter(
    e => e.energy > 0 && !eaten.has(e.id)
  );

  return {
    entities: [...survivors, ...newEntities],
    nextId,
    tickCount: state.tickCount + 1,
  };
}
