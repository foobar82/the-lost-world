import { useRef, useEffect, useCallback } from 'react';
import { SimulationConfig, SimulationState } from '../simulation/types';
import { createInitialState, tick } from '../simulation/engine';
import { render } from '../simulation/renderer';
import { defaultConfig } from '../simulation/config';

interface Props {
  config?: SimulationConfig;
}

export default function EcosystemCanvas({ config = defaultConfig }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<SimulationState>(createInitialState(config));
  const animFrameRef = useRef<number>(0);
  const lastTickTimeRef = useRef<number>(0);

  const getCanvasSize = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return { width: config.worldWidth, height: config.worldHeight };
    const rect = canvas.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  }, [config]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const tickInterval = 1000 / config.tickRate;
    lastTickTimeRef.current = performance.now();

    function loop(now: number) {
      // Run simulation ticks at fixed rate
      const elapsed = now - lastTickTimeRef.current;
      if (elapsed >= tickInterval) {
        const ticksToRun = Math.min(Math.floor(elapsed / tickInterval), 3);
        for (let i = 0; i < ticksToRun; i++) {
          stateRef.current = tick(stateRef.current, config);
        }
        lastTickTimeRef.current = now - (elapsed % tickInterval);
      }

      // Render every frame
      const { width, height } = getCanvasSize();
      canvas!.width = width * devicePixelRatio;
      canvas!.height = height * devicePixelRatio;
      ctx!.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      render(ctx!, stateRef.current.entities, config, width, height);

      animFrameRef.current = requestAnimationFrame(loop);
    }

    animFrameRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(animFrameRef.current);
    };
  }, [config, getCanvasSize]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100%',
        display: 'block',
        borderRadius: '4px',
        boxShadow: 'inset 0 0 20px rgba(0,0,0,0.3)',
      }}
    />
  );
}
