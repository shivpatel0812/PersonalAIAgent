export type FindRequest = {
  subject: string;
  constraints: Record<string, unknown>;
  status: "ready" | "needs_clarification";
  missing: string[];
  clarifying_question?: string | null;
};

export type FindResult = {
  index: number;
  title: string;
  snippet: string;
  url: string;
  image_url?: string | null;
};

export type FindMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  payload?: {
    request?: FindRequest;
    results?: FindResult[];
    query?: string;
  } | null;
  created_at?: string | null;
};

export type FindTurnResponse = {
  session_id: string;
  phase: "gathering" | "results";
  assistant_message?: string | null;
  request?: FindRequest | null;
  results: FindResult[];
  messages: FindMessage[];
};

export type ThumbFeedback = {
  type: "thumb";
  index: number;
  value: "up" | "down";
};

export type RefineFeedback = {
  type: "refine";
  ratings: Array<{ index: number; value: "up" | "down" }>;
};

export type FindMessageFeedback = ThumbFeedback | RefineFeedback | null;
