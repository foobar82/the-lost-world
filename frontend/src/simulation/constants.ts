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
export const INITIAL_PLANTS = 40;
export const INITIAL_HERBIVORES = 12;
export const INITIAL_PREDATORS = 3;

// Population limits
export const PLANT_CAP = 120;
export const HERBIVORE_CAP = 60;
export const PREDATOR_CAP = 30;
export const RESPAWN_COUNT = 3; // respawn this many when a species hits 0

// Energy
export const MAX_ENERGY = 100;
export const EATING_ENERGY_GAIN = 20;
export const REPRODUCTION_THRESHOLD = 70;
export const REPRODUCTION_COST = 40;

// Plant behaviour
export const PLANT_ENERGY_REGEN = 0.5; // energy gained per tick (photosynthesis)
export const PLANT_ENERGY_DRAIN = 0.05; // passive energy loss per tick
export const PLANT_REPRODUCE_CHANCE = 0.005; // chance per tick
export const PLANT_SPAWN_RADIUS = 50; // max distance offspring can appear from parent
export const PLANT_MAX_DENSITY_RADIUS = 30; // check radius for overcrowding
export const PLANT_MAX_NEIGHBOURS = 5; // max plants within density radius

// Herbivore behaviour
export const HERBIVORE_SPEED = 1.5; // units per tick
export const HERBIVORE_ENERGY_DRAIN = 0.08; // energy lost per tick while moving
export const HERBIVORE_SENSE_RADIUS = 80; // how far they can detect plants
export const HERBIVORE_EAT_RADIUS = 10; // distance at which eating occurs
export const HERBIVORE_REPRODUCE_CHANCE = 0.005; // chance per tick when above threshold
export const HERBIVORE_WANDER_CHANGE = 0.05; // chance to pick a new random direction per tick
export const HERBIVORE_SPAWN_RADIUS = 20; // max distance offspring can appear from parent

// Predator behaviour
export const PREDATOR_SPEED = 1.8; // faster than herbivores
export const PREDATOR_ENERGY_DRAIN = 0.2; // higher metabolic cost
export const PREDATOR_SENSE_RADIUS = 90; // can detect herbivores from further away
export const PREDATOR_EAT_RADIUS = 12;
export const PREDATOR_REPRODUCE_CHANCE = 0.003;
export const PREDATOR_WANDER_CHANGE = 0.04;
export const PREDATOR_SPAWN_RADIUS = 25; // max distance offspring can appear from parent

// Shared physics
export const OFFSPRING_ENERGY_RATIO = 0.5; // fraction of REPRODUCTION_COST given to offspring
export const INITIAL_ENERGY_RATIO = 0.6; // fraction of MAX_ENERGY for newly spawned entities
export const DIRECTION_BOUNCE_RANGE = 0.4; // random scatter when bouncing off edges
export const WANDER_DIRECTION_RANGE = 0.5; // fraction of PI for wander direction change

// Entity rendering sizes (radii / half-sizes in world units)
export const PLANT_RADIUS = 5;
export const HERBIVORE_RADIUS = 6;
export const PREDATOR_SIZE = 7; // half-height of triangle

// Entity alpha (energy-based opacity)
export const ENTITY_ALPHA_MIN = 0.4;
export const ENTITY_ALPHA_RANGE = 0.6;

// Predator triangle geometry
export const PREDATOR_TRIANGLE_BACK_ANGLE = 2.4;
export const PREDATOR_TRIANGLE_BACK_SCALE = 0.8;

// Plateau rendering
export const PLATEAU_CORNER_RADIUS = 12;
export const GRASS_SPOT_COUNT = 120;
export const GRASS_SPOT_MIN_RADIUS = 2;
export const GRASS_SPOT_MAX_RADIUS = 4;

// Water ripple rendering
export const WATER_RIPPLE_LINE_WIDTH = 1;
export const WATER_RIPPLE_OFFSET_X = 5;
export const WATER_RIPPLE_OFFSET_Y = 5;
export const WATER_RIPPLE_SCALE_X = 0.6;
export const WATER_RIPPLE_SCALE_Y = 0.5;
export const WATER_RIPPLE_ROTATION = -0.2;

// Population counter HUD offsets
export const POP_LABEL_HERBIVORE_X = 120;
export const POP_LABEL_PREDATOR_X = 280;

// Plateau boundary inset (entities stay within this margin from canvas edge)
export const PLATEAU_MARGIN = 20;
