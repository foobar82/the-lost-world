import { useRef, useEffect, useState } from "react";
import { useSimulation } from "../simulation";
import { WORLD } from "../simulation/config";

export function EcosystemCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: WORLD.width, height: WORLD.height });

  useSimulation(canvasRef);

  // Responsive: fit canvas to container while preserving aspect ratio
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        const aspect = WORLD.width / WORLD.height;
        const canvasWidth = Math.floor(width);
        const canvasHeight = Math.floor(width / aspect);
        setSize({ width: canvasWidth, height: canvasHeight });
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="ecosystem-container">
      <canvas
        ref={canvasRef}
        width={size.width}
        height={size.height}
        className="ecosystem-canvas"
      />
    </div>
  );
}
