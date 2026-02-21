import { SimulationConfig } from './types';

export const defaultConfig: SimulationConfig = {
  worldWidth: 800,
  worldHeight: 600,
  waterCenter: { x: 400, y: 300 },
  waterRadius: 50,

  initialPlants: 30,
  initialHerbivores: 15,
  initialPredators: 5,

  maxEnergy: 100,
  eatingEnergyGain: 30,
  reproductionThreshold: 70,
  reproductionCost: 40,

  herbivoreSpeed: 2,
  predatorSpeed: 3,

  // Energy drain per tick (at 10 tps: ~1/s for herbivores/predators)
  plantEnergyDrain: 0.02,
  herbivoreEnergyDrain: 0.1,
  predatorEnergyDrain: 0.1,

  plantPhotosynthesisRate: 0.08,

  // ~1 new plant per 5 seconds per plant at 10 tps = every 50 ticks
  plantReproductionInterval: 50,

  herbivoreSenseRadius: 80,
  predatorSenseRadius: 100,

  plantDensityCap: 3,

  tickRate: 10,
};
