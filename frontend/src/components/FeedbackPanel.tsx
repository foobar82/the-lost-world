import { useState, useEffect, useCallback } from "react";
import type { FeedbackItem } from "../api";
import { submitFeedback, fetchFeedback } from "../api";
import "./FeedbackPanel.css";

const POLL_INTERVAL = 30_000;

const STATUS_LABELS: Record<FeedbackItem["status"], string> = {
  pending: "Pending",
  in_progress: "In Progress",
  done: "Done",
  rejected: "Rejected",
};

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + "\u2026" : text;
}

function StatusBadge({ status }: { status: FeedbackItem["status"] }) {
  return <span className={`badge badge--${status}`}>{STATUS_LABELS[status]}</span>;
}

function FeedbackEntry({ item }: { item: FeedbackItem }) {
  return (
    <li className="queue-item">
      <div className="queue-item__header">
        <span className="queue-item__ref">{item.reference}</span>
        <StatusBadge status={item.status} />
      </div>
      <p className="queue-item__content">{truncate(item.content, 120)}</p>
      {item.status === "done" && item.agent_notes && (
        <p className="queue-item__notes">{item.agent_notes}</p>
      )}
    </li>
  );
}

export default function FeedbackPanel() {
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(true);

  const loadItems = useCallback(async () => {
    try {
      const data = await fetchFeedback();
      setItems(data);
      setError(null);
      setConnected(true);
    } catch {
      setError("Could not load feedback queue");
      setConnected(false);
    }
  }, []);

  // Poll every 30s + on page focus
  useEffect(() => {
    loadItems();
    const timer = setInterval(loadItems, POLL_INTERVAL);
    const onFocus = () => loadItems();
    window.addEventListener("focus", onFocus);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [loadItems]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || submitting) return;

    setSubmitting(true);
    setConfirmation(null);
    try {
      const result = await submitFeedback(text);
      setInput("");
      setConfirmation(`Submitted as ${result.reference}`);
      loadItems();
    } catch {
      setConfirmation("Submission failed \u2014 please try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="feedback-panel">
      <h2 className="feedback-panel__heading">
        Field Dispatches
        <span
          className={`connection-dot ${connected ? "connection-dot--ok" : "connection-dot--err"}`}
          title={connected ? "Connected" : "Disconnected"}
        />
      </h2>

      <form className="submit-box" onSubmit={handleSubmit}>
        <label className="submit-box__label" htmlFor="feedback-input">
          What should we add or change?
        </label>
        <div className="submit-box__row">
          <input
            id="feedback-input"
            className="submit-box__input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Add fish to the water\u2026"
            disabled={submitting}
          />
          <button
            className="submit-box__button"
            type="submit"
            disabled={submitting || !input.trim()}
          >
            {submitting ? "Sending\u2026" : "Submit"}
          </button>
        </div>
        {confirmation && (
          <p className="submit-box__confirmation">{confirmation}</p>
        )}
      </form>

      <div className="queue">
        <h3 className="queue__heading">Request Queue</h3>
        {error && <p className="queue__error">{error}</p>}
        {items.length === 0 && !error && (
          <p className="queue__empty">No requests yet. Be the first!</p>
        )}
        <ul className="queue__list">
          {items.map((item) => (
            <FeedbackEntry key={item.id} item={item} />
          ))}
        </ul>
      </div>
    </div>
  );
}
