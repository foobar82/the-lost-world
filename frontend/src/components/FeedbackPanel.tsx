import { useState, useEffect, useCallback } from "react";
import { submitFeedback, fetchFeedback, type FeedbackItem } from "../api";

const STATUS_LABELS: Record<FeedbackItem["status"], { label: string; className: string }> = {
  pending: { label: "Pending", className: "badge-pending" },
  in_progress: { label: "In Progress", className: "badge-in-progress" },
  done: { label: "Done", className: "badge-done" },
  rejected: { label: "Rejected", className: "badge-rejected" },
};

const POLL_INTERVAL = 30_000;

export function FeedbackPanel() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    try {
      const data = await fetchFeedback();
      setItems(data);
    } catch {
      // Silently fail on poll — the user will see stale data
    }
  }, []);

  // Poll for updates
  useEffect(() => {
    loadItems();
    const interval = setInterval(loadItems, POLL_INTERVAL);

    const onFocus = () => loadItems();
    window.addEventListener("focus", onFocus);

    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [loadItems]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const content = input.trim();
    if (!content || submitting) return;

    setSubmitting(true);
    setError(null);
    setConfirmation(null);

    try {
      const result = await submitFeedback(content);
      setConfirmation(`Submitted as ${result.reference}`);
      setInput("");
      loadItems();
    } catch {
      setError("Failed to submit feedback. Is the server running?");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="feedback-panel">
      <h2 className="panel-title">Field Dispatches</h2>
      <p className="panel-subtitle">
        Send observations and requests to the research station.
      </p>

      <form onSubmit={handleSubmit} className="feedback-form">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Add fish to the water source..."
          rows={3}
          className="feedback-input"
          disabled={submitting}
        />
        <button type="submit" className="feedback-submit" disabled={submitting || !input.trim()}>
          {submitting ? "Sending..." : "Send Dispatch"}
        </button>
      </form>

      {confirmation && <div className="feedback-confirmation">{confirmation}</div>}
      {error && <div className="feedback-error">{error}</div>}

      <div className="feedback-queue">
        <h3 className="queue-title">Request Queue</h3>
        {items.length === 0 ? (
          <p className="queue-empty">No dispatches yet. Be the first explorer to send one.</p>
        ) : (
          <ul className="queue-list">
            {items.map((item) => (
              <li key={item.id} className="queue-item">
                <div className="queue-item-header">
                  <span className="queue-ref">{item.reference}</span>
                  <span className={`queue-badge ${STATUS_LABELS[item.status].className}`}>
                    {STATUS_LABELS[item.status].label}
                  </span>
                </div>
                <p className="queue-content">{item.content}</p>
                {item.agent_notes && (
                  <p className="queue-notes">
                    <strong>Notes:</strong> {item.agent_notes}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
