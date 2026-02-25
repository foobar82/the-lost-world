import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import EcosystemCanvas from "../../frontend/src/components/EcosystemCanvas";
import { WORLD_WIDTH } from "../../frontend/src/simulation/constants";

// ---------------------------------------------------------------------------
// jsdom canvas stub — getContext("2d") returns null in jsdom, so we provide a
// minimal no-op CanvasRenderingContext2D that satisfies the drawing calls
// without installing the heavy canvas npm package.
// ---------------------------------------------------------------------------

function createStubContext(): CanvasRenderingContext2D {
  const noop = () => {};

  return new Proxy({} as CanvasRenderingContext2D, {
    get(_target, prop) {
      if (prop === "canvas") return document.createElement("canvas");
      if (prop === "globalAlpha") return 1;
      if (prop === "fillStyle") return "#000";
      if (prop === "strokeStyle") return "#000";
      if (prop === "lineWidth") return 1;
      if (prop === "font") return "10px sans-serif";
      if (prop === "textBaseline") return "alphabetic";

      if (prop === "createLinearGradient" || prop === "createRadialGradient") {
        return () => ({ addColorStop: noop });
      }

      // drawImage, fillRect, arc, beginPath, moveTo, lineTo, etc. → noop
      return noop;
    },
    set() {
      return true;
    },
  });
}

beforeEach(() => {
  // Patch getContext on the prototype so EVERY canvas element (including
  // offscreen canvases created via document.createElement) returns our stub.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    (() => createStubContext()) as typeof HTMLCanvasElement.prototype.getContext,
  );

  // Stub requestAnimationFrame / cancelAnimationFrame so the render loop
  // fires once synchronously and then stops.
  let callCount = 0;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    if (callCount === 0) {
      callCount++;
      cb(performance.now());
    }
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  Object.defineProperty(window, "devicePixelRatio", {
    value: 1,
    writable: true,
  });
});

// ---------------------------------------------------------------------------
// Canvas Initialisation
// ---------------------------------------------------------------------------

describe("Canvas initialisation", () => {
  it("renders a canvas element", () => {
    const { container } = render(<EcosystemCanvas />);
    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
  });

  it("canvas has expected logical dimensions via inline style", () => {
    const { container } = render(<EcosystemCanvas />);
    const canvas = container.querySelector("canvas") as HTMLCanvasElement;

    // The component sets style.maxWidth to WORLD_WIDTH
    expect(canvas.style.maxWidth).toBe(`${WORLD_WIDTH}px`);
  });
});

// ---------------------------------------------------------------------------
// Entity Rendering
// ---------------------------------------------------------------------------

describe("Entity rendering", () => {
  it("does not throw when rendering with default entities", () => {
    // The primary assertion is that render() completes without error.
    // Canvas drawing in jsdom is stubbed as no-ops, but the full code path
    // through drawEntity / drawPlant / drawHerbivore / drawPredator executes.
    expect(() => {
      render(<EcosystemCanvas />);
    }).not.toThrow();
  });
});
