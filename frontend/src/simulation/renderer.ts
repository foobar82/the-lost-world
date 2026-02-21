import { WORLD, WATER_SOURCE, PLANT, HERBIVORE, PREDATOR } from "./config";
import type { Entity } from "./types";

// Colours for the naturalist / Victorian field-station aesthetic
const COLOURS = {
  plateau: "#5a7a3a",
  plateauEdge: "#3d5427",
  cliffShadow: "#2a3a1a",
  water: "#4a8ab5",
  waterHighlight: "#6aaed6",
  plant: "#3a8c3a",
  plantHighlight: "#5cb85c",
  herbivore: "#8b6914",
  herbivoreOutline: "#6b4f0a",
  predator: "#c0392b",
  predatorOutline: "#922b21",
} as const;

export function render(
  ctx: CanvasRenderingContext2D,
  entities: Entity[],
  canvasWidth: number,
  canvasHeight: number,
): void {
  const scaleX = canvasWidth / WORLD.width;
  const scaleY = canvasHeight / WORLD.height;

  ctx.save();
  ctx.scale(scaleX, scaleY);

  drawBackground(ctx);
  drawWater(ctx);
  drawEntities(ctx, entities);

  ctx.restore();
}

// ---------------------------------------------------------------------------
// Background
// ---------------------------------------------------------------------------

function drawBackground(ctx: CanvasRenderingContext2D): void {
  // Main plateau
  ctx.fillStyle = COLOURS.plateau;
  ctx.fillRect(0, 0, WORLD.width, WORLD.height);

  // Cliff edges — darker border to convey a bounded world
  const edgeWidth = 8;
  ctx.strokeStyle = COLOURS.plateauEdge;
  ctx.lineWidth = edgeWidth;
  ctx.strokeRect(edgeWidth / 2, edgeWidth / 2, WORLD.width - edgeWidth, WORLD.height - edgeWidth);

  // Inner shadow for depth
  ctx.strokeStyle = COLOURS.cliffShadow;
  ctx.lineWidth = 2;
  ctx.strokeRect(edgeWidth + 1, edgeWidth + 1, WORLD.width - edgeWidth * 2 - 2, WORLD.height - edgeWidth * 2 - 2);

  // Subtle terrain texture — small random dots
  ctx.fillStyle = "rgba(255, 255, 255, 0.03)";
  for (let i = 0; i < 200; i++) {
    const x = Math.random() * WORLD.width;
    const y = Math.random() * WORLD.height;
    ctx.fillRect(x, y, 2, 2);
  }
}

// ---------------------------------------------------------------------------
// Water source
// ---------------------------------------------------------------------------

function drawWater(ctx: CanvasRenderingContext2D): void {
  // Outer glow
  const gradient = ctx.createRadialGradient(
    WATER_SOURCE.x, WATER_SOURCE.y, WATER_SOURCE.radius * 0.3,
    WATER_SOURCE.x, WATER_SOURCE.y, WATER_SOURCE.radius,
  );
  gradient.addColorStop(0, COLOURS.waterHighlight);
  gradient.addColorStop(1, COLOURS.water);

  ctx.beginPath();
  ctx.arc(WATER_SOURCE.x, WATER_SOURCE.y, WATER_SOURCE.radius, 0, Math.PI * 2);
  ctx.fillStyle = gradient;
  ctx.fill();

  // Subtle highlight
  ctx.beginPath();
  ctx.arc(WATER_SOURCE.x - 8, WATER_SOURCE.y - 8, WATER_SOURCE.radius * 0.25, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(255, 255, 255, 0.15)";
  ctx.fill();
}

// ---------------------------------------------------------------------------
// Entities
// ---------------------------------------------------------------------------

function drawEntities(ctx: CanvasRenderingContext2D, entities: Entity[]): void {
  for (const e of entities) {
    if (!e.alive) continue;
    switch (e.species) {
      case "plant":
        drawPlant(ctx, e);
        break;
      case "herbivore":
        drawHerbivore(ctx, e);
        break;
      case "predator":
        drawPredator(ctx, e);
        break;
    }
  }
}

function drawPlant(ctx: CanvasRenderingContext2D, e: Entity): void {
  const opacity = 0.5 + (e.energy / 100) * 0.5;
  ctx.globalAlpha = opacity;
  ctx.beginPath();
  ctx.arc(e.x, e.y, PLANT.radius, 0, Math.PI * 2);
  ctx.fillStyle = COLOURS.plant;
  ctx.fill();
  ctx.fillStyle = COLOURS.plantHighlight;
  ctx.beginPath();
  ctx.arc(e.x - 1, e.y - 1, PLANT.radius * 0.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawHerbivore(ctx: CanvasRenderingContext2D, e: Entity): void {
  ctx.beginPath();
  ctx.arc(e.x, e.y, HERBIVORE.radius, 0, Math.PI * 2);
  ctx.fillStyle = COLOURS.herbivore;
  ctx.fill();
  ctx.strokeStyle = COLOURS.herbivoreOutline;
  ctx.lineWidth = 1;
  ctx.stroke();
}

function drawPredator(ctx: CanvasRenderingContext2D, e: Entity): void {
  const r = PREDATOR.radius;
  ctx.beginPath();
  ctx.moveTo(e.x, e.y - r);
  ctx.lineTo(e.x - r, e.y + r);
  ctx.lineTo(e.x + r, e.y + r);
  ctx.closePath();
  ctx.fillStyle = COLOURS.predator;
  ctx.fill();
  ctx.strokeStyle = COLOURS.predatorOutline;
  ctx.lineWidth = 1;
  ctx.stroke();
}
