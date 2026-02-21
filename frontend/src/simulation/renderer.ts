import { Entity, Species, SimulationConfig } from './types';

const CLIFF_WIDTH = 16;

// Colors
const PLATEAU_COLOR = '#4a7c3f';
const PLATEAU_EDGE_COLOR = '#3a6232';
const CLIFF_COLOR = '#8b7355';
const CLIFF_SHADOW = '#6b5540';
const WATER_COLOR = 'rgba(70, 140, 200, 0.6)';
const WATER_EDGE_COLOR = 'rgba(50, 110, 170, 0.4)';
const PLANT_COLOR = '#2d8a4e';
const PLANT_OUTLINE = '#1a5c32';
const HERBIVORE_COLOR = '#b08040';
const HERBIVORE_OUTLINE = '#7a5828';
const PREDATOR_COLOR = '#c0392b';
const PREDATOR_OUTLINE = '#8b2a20';

export function render(
  ctx: CanvasRenderingContext2D,
  entities: Entity[],
  config: SimulationConfig,
  canvasWidth: number,
  canvasHeight: number
) {
  const scaleX = canvasWidth / config.worldWidth;
  const scaleY = canvasHeight / config.worldHeight;

  ctx.save();
  ctx.scale(scaleX, scaleY);

  // Clear
  ctx.fillStyle = '#2c1810';
  ctx.fillRect(0, 0, config.worldWidth, config.worldHeight);

  // Draw cliff edges (the "bounded world" feel)
  drawCliffs(ctx, config);

  // Draw plateau surface
  drawPlateau(ctx, config);

  // Draw water source
  drawWater(ctx, config);

  // Draw entities (plants first, then herbivores, then predators on top)
  const plants = entities.filter(e => e.species === Species.Plant);
  const herbivores = entities.filter(e => e.species === Species.Herbivore);
  const predators = entities.filter(e => e.species === Species.Predator);

  for (const plant of plants) drawPlant(ctx, plant);
  for (const herb of herbivores) drawHerbivore(ctx, herb);
  for (const pred of predators) drawPredator(ctx, pred);

  ctx.restore();
}

function drawCliffs(ctx: CanvasRenderingContext2D, config: SimulationConfig) {
  const w = config.worldWidth;
  const h = config.worldHeight;

  // Outer cliff shadow
  ctx.fillStyle = CLIFF_SHADOW;
  ctx.fillRect(0, 0, w, CLIFF_WIDTH);
  ctx.fillRect(0, h - CLIFF_WIDTH, w, CLIFF_WIDTH);
  ctx.fillRect(0, 0, CLIFF_WIDTH, h);
  ctx.fillRect(w - CLIFF_WIDTH, 0, CLIFF_WIDTH, h);

  // Inner cliff
  ctx.fillStyle = CLIFF_COLOR;
  ctx.fillRect(4, 4, w - 8, CLIFF_WIDTH - 6);
  ctx.fillRect(4, h - CLIFF_WIDTH + 2, w - 8, CLIFF_WIDTH - 6);
  ctx.fillRect(4, 4, CLIFF_WIDTH - 6, h - 8);
  ctx.fillRect(w - CLIFF_WIDTH + 2, 4, CLIFF_WIDTH - 6, h - 8);
}

function drawPlateau(ctx: CanvasRenderingContext2D, config: SimulationConfig) {
  const w = config.worldWidth;
  const h = config.worldHeight;

  // Main plateau surface
  ctx.fillStyle = PLATEAU_COLOR;
  ctx.fillRect(CLIFF_WIDTH, CLIFF_WIDTH, w - CLIFF_WIDTH * 2, h - CLIFF_WIDTH * 2);

  // Subtle edge shading
  ctx.fillStyle = PLATEAU_EDGE_COLOR;
  ctx.fillRect(CLIFF_WIDTH, CLIFF_WIDTH, w - CLIFF_WIDTH * 2, 4);
  ctx.fillRect(CLIFF_WIDTH, CLIFF_WIDTH, 4, h - CLIFF_WIDTH * 2);

  // Texture: scatter some slightly different green dots
  ctx.fillStyle = 'rgba(60, 140, 60, 0.15)';
  // Use deterministic positions for texture
  for (let i = 0; i < 80; i++) {
    const tx = CLIFF_WIDTH + 10 + ((i * 97) % (w - CLIFF_WIDTH * 2 - 20));
    const ty = CLIFF_WIDTH + 10 + ((i * 131) % (h - CLIFF_WIDTH * 2 - 20));
    ctx.beginPath();
    ctx.arc(tx, ty, 3 + (i % 4), 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawWater(ctx: CanvasRenderingContext2D, config: SimulationConfig) {
  const { x, y } = config.waterCenter;
  const r = config.waterRadius;

  // Water outer glow
  ctx.fillStyle = WATER_EDGE_COLOR;
  ctx.beginPath();
  ctx.arc(x, y, r + 6, 0, Math.PI * 2);
  ctx.fill();

  // Water body
  ctx.fillStyle = WATER_COLOR;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();

  // Water highlight
  ctx.fillStyle = 'rgba(160, 210, 240, 0.3)';
  ctx.beginPath();
  ctx.arc(x - r * 0.2, y - r * 0.2, r * 0.4, 0, Math.PI * 2);
  ctx.fill();
}

function drawPlant(ctx: CanvasRenderingContext2D, entity: Entity) {
  const size = 4 + (entity.energy / 100) * 3; // Size varies with energy
  ctx.fillStyle = PLANT_COLOR;
  ctx.strokeStyle = PLANT_OUTLINE;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(entity.x, entity.y, size, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

function drawHerbivore(ctx: CanvasRenderingContext2D, entity: Entity) {
  const size = 5 + (entity.energy / 100) * 2;
  ctx.fillStyle = HERBIVORE_COLOR;
  ctx.strokeStyle = HERBIVORE_OUTLINE;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(entity.x, entity.y, size, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

function drawPredator(ctx: CanvasRenderingContext2D, entity: Entity) {
  const size = 6 + (entity.energy / 100) * 2;
  // Draw as triangle
  ctx.fillStyle = PREDATOR_COLOR;
  ctx.strokeStyle = PREDATOR_OUTLINE;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(entity.x, entity.y - size);
  ctx.lineTo(entity.x - size * 0.866, entity.y + size * 0.5);
  ctx.lineTo(entity.x + size * 0.866, entity.y + size * 0.5);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
}
