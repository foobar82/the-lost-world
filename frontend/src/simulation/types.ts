export enum Species {
  Plant = 'plant',
  Herbivore = 'herbivore',
  Predator = 'predator',
}

export interface Entity {
  id: number;
  species: Species;
  x: number;
  y: number;
  energy: number;
  age: number; // ticks alive
}

export interface SimulationConfig {
  worldWidth: number;
  worldHeight: number;
  waterCenter: { x: number; y: number };
  waterRadius: number;

  // Initial populations
  initialPlants: number;
  initialHerbivores: number;
  initialPredators: number;

  // Energy
  maxEnergy: number;
  eatingEnergyGain: number;
  reproductionThreshold: number;
  reproductionCost: number;

  // Movement speeds (pixels per tick)
  herbivoreSpeed: number;
  predatorSpeed: number;

  // Energy drain per tick
  plantEnergyDrain: number;
  herbivoreEnergyDrain: number;
  predatorEnergyDrain: number;

  // Plant photosynthesis gain per tick
  plantPhotosynthesisRate: number;

  // Reproduction cooldown (ticks)
  plantReproductionInterval: number;

  // Sensing radius for finding food
  herbivoreSenseRadius: number;
  predatorSenseRadius: number;

  // Maximum population density for plants (per 100x100 area)
  plantDensityCap: number;

  // Tick rate (ticks per second)
  tickRate: number;
}

export interface SimulationState {
  entities: Entity[];
  nextId: number;
  tickCount: number;
}
