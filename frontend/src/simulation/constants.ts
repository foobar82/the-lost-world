// World dimensions (logical units, not pixels)
export const WORLD_WIDTH = 800;
export const WORLD_HEIGHT = 600;

// Simulation timing
export const TICK_RATE = 10; // ticks per second
export const TICK_INTERVAL = 1000 / TICK_RATE; // ms between ticks

// Water source (centred, elliptical)
export const WATER_X = 420;
export const WATER_Y = 280;
export const WATER_RADIUS_X = 60;
export const WATER_RADIUS_Y = 40;

// Initial population counts
export const INITIAL_PLANTS = 30;
export const INITIAL_HERBIVORES = 15;
export const INITIAL_PREDATORS = 5;

// Energy
export const MAX_ENERGY = 100;
export const EATING_ENERGY_GAIN = 30;
export const REPRODUCTION_THRESHOLD = 70;
export const REPRODUCTION_COST = 40;

// Plant behaviour
export const PLANT_ENERGY_REGEN = 0.3; // energy gained per tick (photosynthesis)
export const PLANT_ENERGY_DRAIN = 0.05; // passive energy loss per tick
export const PLANT_REPRODUCE_CHANCE = 0.002; // chance per tick (~1 new plant per 5s at 10 tps)
export const PLANT_SPAWN_RADIUS = 40; // max distance offspring can appear from parent
export const PLANT_MAX_DENSITY_RADIUS = 30; // check radius for overcrowding
export const PLANT_MAX_NEIGHBOURS = 4; // max plants within density radius

// Herbivore behaviour
export const HERBIVORE_SPEED = 1.5; // units per tick
export const HERBIVORE_ENERGY_DRAIN = 0.1; // energy lost per tick while moving
export const HERBIVORE_SENSE_RADIUS = 80; // how far they can detect plants
export const HERBIVORE_EAT_RADIUS = 10; // distance at which eating occurs
export const HERBIVORE_REPRODUCE_CHANCE = 0.005; // chance per tick when above threshold
export const HERBIVORE_WANDER_CHANGE = 0.05; // chance to pick a new random direction per tick

// Predator behaviour
export const PREDATOR_SPEED = 2.2; // faster than herbivores
export const PREDATOR_ENERGY_DRAIN = 0.15; // higher metabolic cost
export const PREDATOR_SENSE_RADIUS = 120; // can detect herbivores from further away
export const PREDATOR_EAT_RADIUS = 12;
export const PREDATOR_REPRODUCE_CHANCE = 0.003;
export const PREDATOR_WANDER_CHANGE = 0.04;

// Entity rendering sizes (radii / half-sizes in world units)
export const PLANT_RADIUS = 5;
export const HERBIVORE_RADIUS = 6;
export const PREDATOR_SIZE = 7; // half-height of triangle

// Plateau boundary inset (entities stay within this margin from canvas edge)
export const PLATEAU_MARGIN = 20;
