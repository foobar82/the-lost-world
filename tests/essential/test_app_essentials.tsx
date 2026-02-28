// ESSENTIAL TESTS - Human-maintained only
// These tests validate contract.md invariants
// Agents must not modify these files
//
// Coverage notes:
//   - "App renders without crashing" — NEW (no existing test renders the top-level App)
//   - "Ecosystem canvas element is present" — NEW via App (canvas.test.tsx tests
//     EcosystemCanvas in isolation, not through the composed App)
//   - "Feedback text box is present and accepts input" — NEW via App (feedback.test.tsx
//     tests FeedbackPanel in isolation)
//   - "Request queue component is present" — NEW via App
//   - "No console errors on initial load" — NEW

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../../frontend/src/App";

// ---------------------------------------------------------------------------
// Stubs — canvas & animation (jsdom has no canvas/rAF support)
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
      return noop;
    },
    set() {
      return true;
    },
  });
}

// Mock the API so FeedbackPanel doesn't make real network calls
vi.mock("../../frontend/src/api", () => ({
  submitFeedback: vi.fn(),
  fetchFeedback: vi.fn().mockResolvedValue([]),
}));

let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    (() => createStubContext()) as typeof HTMLCanvasElement.prototype.getContext,
  );

  let rafCount = 0;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    if (rafCount === 0) {
      rafCount++;
      cb(performance.now());
    }
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());

  Object.defineProperty(window, "devicePixelRatio", {
    value: 1,
    writable: true,
  });

  consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  consoleErrorSpy.mockRestore();
});

// ---------------------------------------------------------------------------
// App-level integration tests
// ---------------------------------------------------------------------------

describe("App essentials", () => {
  it("renders without crashing", () => {
    expect(() => {
      render(<App />);
    }).not.toThrow();
  });

  it("ecosystem canvas element is present", () => {
    const { container } = render(<App />);
    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
  });

  it("feedback text box is present and accepts input", async () => {
    const user = userEvent.setup();
    render(<App />);

    const input = screen.getByPlaceholderText(/add fish/i);
    expect(input).toBeInTheDocument();

    await user.type(input, "Hello plateau");
    expect(input).toHaveValue("Hello plateau");
  });

  it("request queue component is present", () => {
    render(<App />);
    expect(screen.getByText("Request Queue")).toBeInTheDocument();
  });

  it("no console errors on initial load", () => {
    render(<App />);
    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });
});
