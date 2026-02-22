export interface FeedbackItem {
  id: number;
  reference: string;
  content: string;
  status: "pending" | "in_progress" | "done" | "rejected";
  agent_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackCreated {
  reference: string;
  status: string;
}

export async function submitFeedback(content: string): Promise<FeedbackCreated> {
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`Submit failed: ${res.status}`);
  return res.json();
}

export async function fetchFeedback(): Promise<FeedbackItem[]> {
  const res = await fetch("/api/feedback");
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return res.json();
}
