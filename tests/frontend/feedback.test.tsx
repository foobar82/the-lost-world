import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FeedbackPanel from "../../frontend/src/components/FeedbackPanel";
import type { FeedbackItem, FeedbackCreated } from "../../frontend/src/api";

// Mock the api module so no real network requests are made
vi.mock("../../frontend/src/api", () => ({
  submitFeedback: vi.fn(),
  fetchFeedback: vi.fn(),
}));

// Import the mocked functions so we can configure them per-test
import { submitFeedback, fetchFeedback } from "../../frontend/src/api";
const mockSubmitFeedback = vi.mocked(submitFeedback);
const mockFetchFeedback = vi.mocked(fetchFeedback);

beforeEach(() => {
  vi.clearAllMocks();
  // Default: empty queue, no errors
  mockFetchFeedback.mockResolvedValue([]);
});

// ---------------------------------------------------------------------------
// Feedback Submission
// ---------------------------------------------------------------------------

describe("Feedback submission", () => {
  it("calls the API with correct payload when submitting feedback", async () => {
    const user = userEvent.setup();
    mockSubmitFeedback.mockResolvedValue({
      reference: "LW-042",
      status: "pending",
    });

    render(<FeedbackPanel />);

    const input = screen.getByPlaceholderText(/add fish/i);
    await user.type(input, "Add butterflies to the meadow");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    expect(mockSubmitFeedback).toHaveBeenCalledWith(
      "Add butterflies to the meadow",
    );
  });

  it("clears the input after a successful submission", async () => {
    const user = userEvent.setup();
    mockSubmitFeedback.mockResolvedValue({
      reference: "LW-042",
      status: "pending",
    });

    render(<FeedbackPanel />);

    const input = screen.getByPlaceholderText(/add fish/i);
    await user.type(input, "More trees please");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(input).toHaveValue("");
    });
  });

  it("shows a confirmation message with the reference number", async () => {
    const user = userEvent.setup();
    mockSubmitFeedback.mockResolvedValue({
      reference: "LW-099",
      status: "pending",
    });

    render(<FeedbackPanel />);

    const input = screen.getByPlaceholderText(/add fish/i);
    await user.type(input, "Bigger predators");
    await user.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/LW-099/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Queue Display
// ---------------------------------------------------------------------------

describe("Queue display", () => {
  const mockItems: FeedbackItem[] = [
    {
      id: 1,
      reference: "LW-001",
      content: "Add fish to the water",
      status: "pending",
      agent_notes: null,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
    {
      id: 2,
      reference: "LW-002",
      content: "Make herbivores faster",
      status: "done",
      agent_notes: "Increased herbivore speed from 1.5 to 2.0",
      created_at: "2025-01-02T00:00:00Z",
      updated_at: "2025-01-03T00:00:00Z",
    },
    {
      id: 3,
      reference: "LW-003",
      content: "Remove the water feature",
      status: "rejected",
      agent_notes: null,
      created_at: "2025-01-04T00:00:00Z",
      updated_at: "2025-01-04T00:00:00Z",
    },
  ];

  it("displays all feedback items from the queue", async () => {
    mockFetchFeedback.mockResolvedValue(mockItems);
    render(<FeedbackPanel />);

    await waitFor(() => {
      expect(screen.getByText("LW-001")).toBeInTheDocument();
      expect(screen.getByText("LW-002")).toBeInTheDocument();
      expect(screen.getByText("LW-003")).toBeInTheDocument();
    });
  });

  it("renders correct status badges for each item", async () => {
    mockFetchFeedback.mockResolvedValue(mockItems);
    render(<FeedbackPanel />);

    await waitFor(() => {
      expect(screen.getByText("Pending")).toBeInTheDocument();
      expect(screen.getByText("Done")).toBeInTheDocument();
      expect(screen.getByText("Rejected")).toBeInTheDocument();
    });
  });

  it("displays agent notes for completed items", async () => {
    mockFetchFeedback.mockResolvedValue(mockItems);
    render(<FeedbackPanel />);

    await waitFor(() => {
      expect(
        screen.getByText("Increased herbivore speed from 1.5 to 2.0"),
      ).toBeInTheDocument();
    });
  });

  it("does not display agent notes for non-done items even if present", async () => {
    const itemsWithNotes: FeedbackItem[] = [
      {
        id: 4,
        reference: "LW-004",
        content: "Add weather",
        status: "pending",
        agent_notes: "This should not render",
        created_at: "2025-01-05T00:00:00Z",
        updated_at: "2025-01-05T00:00:00Z",
      },
    ];
    mockFetchFeedback.mockResolvedValue(itemsWithNotes);
    render(<FeedbackPanel />);

    await waitFor(() => {
      expect(screen.getByText("LW-004")).toBeInTheDocument();
    });

    expect(screen.queryByText("This should not render")).not.toBeInTheDocument();
  });
});
