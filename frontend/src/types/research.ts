export type SearchResult = {
  title: string;
  snippet: string;
  url: string;
};

export type AgentStep = {
  iteration: number;
  action: "search" | "scrape" | "answer" | "error";
  llm_response: string;
  query?: string | null;
  url?: string | null;
  search_results?: SearchResult[] | null;
  scraped_content?: string | null;
  scraped_title?: string | null;
  content_truncated?: boolean | null;
};

export type PastRunMemory = {
  id: string;
  question: string;
  answer_preview: string;
  created_at: string;
  relevance_score: number;
  search_method: "vector" | "keyword";
};

export type ResearchResponse = {
  run_id: string | null;
  question: string;
  answer: string;
  iterations: number;
  steps: AgentStep[];
  saved: boolean;
  memory_runs: PastRunMemory[];
};

export type SavedChat = {
  id: string;
  question: string;
  answer: string;
  steps: AgentStep[];
  iterations: number;
  memory_runs: PastRunMemory[];
  created_at: string;
  saved: boolean;
};

export type ResearchStatus = "idle" | "loading" | "success" | "error";

export type SourceItem = {
  id: string;
  title: string;
  url: string;
  domain: string;
};

export type ResearchSettings = {
  accentColor: string;
  maxSearches: number;
  placeholder: string;
};

export type StreamEventStep = {
  type: "step";
  step: AgentStep;
};

export type StreamEventMemory = {
  type: "memory";
  runs: PastRunMemory[];
};

export type StreamEventComplete = {
  type: "complete";
  question: string;
  answer: string;
  iterations: number;
  steps: AgentStep[];
  memory_runs?: PastRunMemory[];
};

export type StreamEventError = {
  type: "error";
  error: string;
};

export type StreamEventSaved = {
  type: "saved";
  run_id: string;
};

export type StreamEvent =
  | StreamEventStep
  | StreamEventMemory
  | StreamEventComplete
  | StreamEventError
  | StreamEventSaved;
