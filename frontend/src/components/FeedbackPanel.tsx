import { useState, useEffect, useCallback } from 'react';

interface FeedbackItem {
  id: number;
  reference: string;
  content: string;
  status: string;
  agent_notes: string | null;
  created_at: string;
  updated_at: string;
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: '#a0998c', text: '#fff' },
  in_progress: { bg: '#d4a843', text: '#fff' },
  done: { bg: '#4a8c5c', text: '#fff' },
  rejected: { bg: '#b04040', text: '#fff' },
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  done: 'Done',
  rejected: 'Rejected',
};

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.pending;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '3px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.5px',
        textTransform: 'uppercase',
        backgroundColor: colors.bg,
        color: colors.text,
      }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export default function FeedbackPanel() {
  const [content, setContent] = useState('');
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [confirmation, setConfirmation] = useState<string | null>(null);

  const fetchFeedback = useCallback(async () => {
    try {
      const res = await fetch('/api/feedback');
      if (res.ok) {
        const data = await res.json();
        setItems(data);
      }
    } catch {
      // Silently fail — the queue will refresh on next poll
    }
  }, []);

  // Poll for updates every 30 seconds
  useEffect(() => {
    fetchFeedback();
    const interval = setInterval(fetchFeedback, 30000);

    const handleFocus = () => fetchFeedback();
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchFeedback]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || submitting) return;

    setSubmitting(true);
    setConfirmation(null);

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content.trim() }),
      });

      if (res.ok) {
        const data = await res.json();
        setConfirmation(`Submitted as ${data.reference}`);
        setContent('');
        fetchFeedback();
      }
    } catch {
      setConfirmation('Failed to submit — please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Submit box */}
      <div style={{ padding: '16px', borderBottom: '1px solid #d4c9a8' }}>
        <h3
          style={{
            margin: '0 0 10px 0',
            fontFamily: "'Georgia', 'Times New Roman', serif",
            fontSize: '16px',
            color: '#3a2f20',
          }}
        >
          Submit Feedback
        </h3>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Suggest a change to the ecosystem..."
            maxLength={2000}
            rows={3}
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #c4b896',
              borderRadius: '4px',
              backgroundColor: '#faf6eb',
              fontFamily: "'Georgia', serif",
              fontSize: '14px',
              color: '#3a2f20',
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />
          <button
            type="submit"
            disabled={!content.trim() || submitting}
            style={{
              alignSelf: 'flex-end',
              padding: '8px 20px',
              backgroundColor: submitting ? '#a0998c' : '#4a7c3f',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontFamily: "'Georgia', serif",
              fontSize: '14px',
              cursor: submitting ? 'not-allowed' : 'pointer',
            }}
          >
            {submitting ? 'Submitting...' : 'Submit'}
          </button>
        </form>
        {confirmation && (
          <p
            style={{
              margin: '8px 0 0',
              fontSize: '13px',
              color: confirmation.startsWith('Failed') ? '#b04040' : '#4a7c3f',
              fontStyle: 'italic',
            }}
          >
            {confirmation}
          </p>
        )}
      </div>

      {/* Request queue */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        <h3
          style={{
            margin: '0 0 10px 0',
            fontFamily: "'Georgia', 'Times New Roman', serif",
            fontSize: '16px',
            color: '#3a2f20',
          }}
        >
          Request Queue
        </h3>
        {items.length === 0 ? (
          <p
            style={{
              color: '#8a7e6b',
              fontStyle: 'italic',
              fontSize: '14px',
            }}
          >
            No submissions yet. Be the first to shape this world.
          </p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {items.map(item => (
              <li
                key={item.id}
                style={{
                  padding: '10px 12px',
                  marginBottom: '8px',
                  backgroundColor: '#faf6eb',
                  border: '1px solid #d4c9a8',
                  borderRadius: '4px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '4px',
                  }}
                >
                  <span
                    style={{
                      fontFamily: 'monospace',
                      fontSize: '12px',
                      color: '#6b5d4a',
                      fontWeight: 600,
                    }}
                  >
                    {item.reference}
                  </span>
                  <StatusBadge status={item.status} />
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: '14px',
                    color: '#3a2f20',
                    lineHeight: 1.4,
                  }}
                >
                  {item.content.length > 120
                    ? item.content.slice(0, 120) + '...'
                    : item.content}
                </p>
                {item.agent_notes && (
                  <p
                    style={{
                      margin: '6px 0 0',
                      fontSize: '12px',
                      color: '#6b5d4a',
                      fontStyle: 'italic',
                      borderTop: '1px solid #e8e0cc',
                      paddingTop: '6px',
                    }}
                  >
                    {item.agent_notes}
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
