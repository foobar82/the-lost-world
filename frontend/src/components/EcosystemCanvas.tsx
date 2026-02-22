import { useRef, useEffect } from "react";
import { Simulation } from "../simulation/simulation";
import { Species } from "../simulation/types";
import type { Entity } from "../simulation/types";
import {
  WORLD_WIDTH,
  WORLD_HEIGHT,
  TICK_INTERVAL,
  WATER_X,
  WATER_Y,
  WATER_RADIUS_X,
  WATER_RADIUS_Y,
  PLATEAU_MARGIN,
  PLANT_RADIUS,
  HERBIVORE_RADIUS,
  PREDATOR_SIZE,
} from "../simulation/constants";

// Colours
const CLIFF_COLOUR = "#6B4F3A";
const PLATEAU_COLOUR = "#4A7C3F";
const WATER_COLOUR = "rgba(70, 140, 200, 0.6)";
const PLANT_COLOUR = "#2D8C2D";
const HERBIVORE_COLOUR = "#8B6914";
const PREDATOR_COLOUR = "#C0392B";

function drawPlateau(ctx: CanvasRenderingContext2D): void {
  const w = WORLD_WIDTH;
  const h = WORLD_HEIGHT;
  const m = PLATEAU_MARGIN;

  // Cliff border (full canvas background)
  ctx.fillStyle = CLIFF_COLOUR;
  ctx.fillRect(0, 0, w, h);

  // Cliff edge highlights — draw a subtle 3D ridge around the plateau
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "#8B7355");
  grad.addColorStop(0.3, "#6B4F3A");
  grad.addColorStop(1, "#4A3728");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // Inner plateau surface
  ctx.fillStyle = PLATEAU_COLOUR;
  ctx.beginPath();
  // Rounded rectangle for the plateau edge
  const r = 12;
  ctx.moveTo(m + r, m);
  ctx.lineTo(w - m - r, m);
  ctx.quadraticCurveTo(w - m, m, w - m, m + r);
  ctx.lineTo(w - m, h - m - r);
  ctx.quadraticCurveTo(w - m, h - m, w - m - r, h - m);
  ctx.lineTo(m + r, h - m);
  ctx.quadraticCurveTo(m, h - m, m, h - m - r);
  ctx.lineTo(m, m + r);
  ctx.quadraticCurveTo(m, m, m + r, m);
  ctx.closePath();
  ctx.fill();

  // Subtle grass texture — scattered slightly lighter spots
  ctx.fillStyle = "rgba(90, 160, 70, 0.15)";
  for (let i = 0; i < 120; i++) {
    const gx = m + Math.random() * (w - 2 * m);
    const gy = m + Math.random() * (h - 2 * m);
    ctx.beginPath();
    ctx.arc(gx, gy, 2 + Math.random() * 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawWater(ctx: CanvasRenderingContext2D): void {
  ctx.save();
  ctx.fillStyle = WATER_COLOUR;
  ctx.beginPath();
  ctx.ellipse(WATER_X, WATER_Y, WATER_RADIUS_X, WATER_RADIUS_Y, 0, 0, Math.PI * 2);
  ctx.fill();

  // Light ripple highlight
  ctx.strokeStyle = "rgba(180, 220, 255, 0.4)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(
    WATER_X - 5,
    WATER_Y - 5,
    WATER_RADIUS_X * 0.6,
    WATER_RADIUS_Y * 0.5,
    -0.2,
    0,
    Math.PI * 2
  );
  ctx.stroke();
  ctx.restore();
}

function drawPlant(ctx: CanvasRenderingContext2D, e: Entity): void {
  const alpha = 0.4 + (e.energy / 100) * 0.6;
  ctx.fillStyle = PLANT_COLOUR;
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  ctx.arc(e.x, e.y, PLANT_RADIUS, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawHerbivore(ctx: CanvasRenderingContext2D, e: Entity): void {
  const alpha = 0.4 + (e.energy / 100) * 0.6;
  ctx.fillStyle = HERBIVORE_COLOUR;
  ctx.globalAlpha = alpha;
  ctx.beginPath();
  ctx.arc(e.x, e.y, HERBIVORE_RADIUS, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawPredator(ctx: CanvasRenderingContext2D, e: Entity): void {
  const alpha = 0.4 + (e.energy / 100) * 0.6;
  ctx.fillStyle = PREDATOR_COLOUR;
  ctx.globalAlpha = alpha;

  // Triangle pointing in the direction of movement
  const size = PREDATOR_SIZE;
  const dir = e.direction;
  ctx.beginPath();
  // Tip of the triangle (front)
  ctx.moveTo(e.x + Math.cos(dir) * size, e.y + Math.sin(dir) * size);
  // Back-left
  ctx.lineTo(
    e.x + Math.cos(dir + 2.4) * size * 0.8,
    e.y + Math.sin(dir + 2.4) * size * 0.8
  );
  // Back-right
  ctx.lineTo(
    e.x + Math.cos(dir - 2.4) * size * 0.8,
    e.y + Math.sin(dir - 2.4) * size * 0.8
  );
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawEntity(ctx: CanvasRenderingContext2D, e: Entity): void {
  switch (e.species) {
    case Species.Plant:
      drawPlant(ctx, e);
      break;
    case Species.Herbivore:
      drawHerbivore(ctx, e);
      break;
    case Species.Predator:
      drawPredator(ctx, e);
      break;
  }
}

function drawPopulationCounter(
  ctx: CanvasRenderingContext2D,
  counts: { plants: number; herbivores: number; predators: number }
): void {
  ctx.save();
  ctx.font = "12px monospace";
  ctx.textBaseline = "top";
  const y = WORLD_HEIGHT - PLATEAU_MARGIN + 4;

  ctx.fillStyle = PLANT_COLOUR;
  ctx.fillText(`Plants: ${counts.plants}`, PLATEAU_MARGIN, y);

  ctx.fillStyle = HERBIVORE_COLOUR;
  ctx.fillText(`Herbivores: ${counts.herbivores}`, PLATEAU_MARGIN + 120, y);

  ctx.fillStyle = PREDATOR_COLOUR;
  ctx.fillText(`Predators: ${counts.predators}`, PLATEAU_MARGIN + 280, y);

  ctx.restore();
}

export default function EcosystemCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const simRef = useRef<Simulation | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const sim = new Simulation();
    simRef.current = sim;

    // HiDPI: scale the backing store so rendering is sharp on Retina displays
    const dpr = window.devicePixelRatio || 1;
    canvas.width = WORLD_WIDTH * dpr;
    canvas.height = WORLD_HEIGHT * dpr;

    // Pre-render the static background (plateau + water) to an offscreen canvas
    // so the random grass texture doesn't flicker every frame.
    const bgCanvas = document.createElement("canvas");
    bgCanvas.width = WORLD_WIDTH * dpr;
    bgCanvas.height = WORLD_HEIGHT * dpr;
    const bgCtx = bgCanvas.getContext("2d")!;
    bgCtx.scale(dpr, dpr);
    drawPlateau(bgCtx);
    drawWater(bgCtx);

    // --- Render loop with integrated fixed-timestep simulation ---
    const MAX_CATCHUP_TICKS = 10;
    let lastTime = performance.now();
    let animId: number;

    function render(now: number) {
      const elapsed = now - lastTime;
      lastTime = now;

      // Run simulation ticks for elapsed time, capped to prevent burst
      // processing after tab backgrounding
      const ticks = Math.min(
        Math.floor(elapsed / TICK_INTERVAL),
        MAX_CATCHUP_TICKS,
      );
      for (let i = 0; i < ticks; i++) {
        sim.tick();
      }

      const ctx = canvas!.getContext("2d");
      if (!ctx) return;

      // Reset transform and blit the pre-scaled background at native resolution
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(bgCanvas, 0, 0);

      // Scale so all entity/HUD drawing uses logical coordinates
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Entities
      for (const e of sim.entities) {
        drawEntity(ctx, e);
      }

      // HUD
      drawPopulationCounter(ctx, sim.populationCounts);

      animId = requestAnimationFrame(render);
    }

    animId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: "100%",
        maxWidth: WORLD_WIDTH,
        height: "auto",
        display: "block",
        borderRadius: 8,
        boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
      }}
    />
  );
}
