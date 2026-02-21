/** Simulation configuration — all tunable parameters in one place. */

export const WORLD = {
  width: 800,
  height: 600,
} as const;

export const WATER_SOURCE = {
  x: WORLD.width * 0.5,
  y: WORLD.height * 0.45,
  radius: 45,
} as const;

/** Ticks per second (decoupled from frame rate). */
export const TICK_RATE = 10;

export const INITIAL_COUNTS = {
  plants: 30,
  herbivores: 15,
  predators: 5,
} as const;

export const ENERGY = {
  max: 100,
  reproductionThreshold: 70,
  reproductionCost: 40,
  eatingGain: 30,
} as const;

export const PLANT = {
  /** Average ticks between reproduction attempts. */
  reproductionInterval: 50, // ~5 seconds at 10 tps
  /** Maximum plants in the world before reproduction stops. */
  densityCap: 120,
  /** Energy gained per tick from photosynthesis. */
  photosynthesisRate: 0.15,
  /** Energy lost per tick (slow decay). */
  decayRate: 0.03,
  /** Spawn radius for offspring. */
  spawnRadius: 60,
  /** Visual radius. */
  radius: 5,
} as const;

export const HERBIVORE = {
  /** Movement speed in pixels per tick. */
  speed: 1.8,
  /** Energy drain per tick while moving. */
  energyDrain: 0.1,
  /** Detection radius for seeking food. */
  senseRadius: 80,
  /** Distance at which eating occurs. */
  eatRadius: 10,
  /** Visual radius. */
  radius: 6,
  /** Spawn radius for offspring. */
  spawnRadius: 30,
} as const;

export const PREDATOR = {
  /** Movement speed in pixels per tick (faster than herbivores). */
  speed: 2.5,
  /** Energy drain per tick while moving. */
  energyDrain: 0.15,
  /** Detection radius for seeking prey. */
  senseRadius: 120,
  /** Distance at which eating occurs. */
  eatRadius: 12,
  /** Visual radius. */
  radius: 7,
  /** Spawn radius for offspring. */
  spawnRadius: 30,
} as const;
