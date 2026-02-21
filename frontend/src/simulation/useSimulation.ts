import { useRef, useEffect, useCallback } from "react";
import { TICK_RATE } from "./config";
import { createInitialState, tick } from "./engine";
import { render } from "./renderer";
import type { SimulationState } from "./types";

/**
 * Hook that drives the simulation loop.
 * - Runs simulation ticks at a fixed rate (TICK_RATE per second).
 * - Renders via requestAnimationFrame, decoupled from tick rate.
 */
export function useSimulation(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
  const stateRef = useRef<SimulationState>(createInitialState());
  const lastTickTime = useRef(0);
  const rafId = useRef(0);

  const loop = useCallback(
    (timestamp: number) => {
      const tickInterval = 1000 / TICK_RATE;

      // Run as many ticks as needed to catch up
      if (lastTickTime.current === 0) lastTickTime.current = timestamp;
      while (timestamp - lastTickTime.current >= tickInterval) {
        stateRef.current = tick(stateRef.current);
        lastTickTime.current += tickInterval;
      }

      // Render
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) {
          render(ctx, stateRef.current.entities, canvas.width, canvas.height);
        }
      }

      rafId.current = requestAnimationFrame(loop);
    },
    [canvasRef],
  );

  useEffect(() => {
    rafId.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId.current);
  }, [loop]);

  /** Reset the simulation to fresh initial state. */
  const reset = useCallback(() => {
    stateRef.current = createInitialState();
    lastTickTime.current = 0;
  }, []);

  return { reset };
}
