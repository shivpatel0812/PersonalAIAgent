import type { AgentStep } from "./research";

export type PageType = "stocks" | "personal" | "general";

export type PageConfig = {
  type: PageType;
  title: string;
  description: string;
  placeholder: string;
};

export const RESEARCH_PAGES: PageConfig[] = [
  {
    type: "stocks",
    title: "Stock Research",
    description: "Portfolio, markets, and investment research",
    placeholder: "Ask about a stock, sector, or market trend…",
  },
  {
    type: "personal",
    title: "Personal Assistant",
    description: "Your general personal research and planning assistant",
    placeholder: "What can I help you with?",
  },
  {
    type: "general",
    title: "General Research",
    description: "Open-ended research on any topic",
    placeholder: "Ask anything…",
  },
];

export function getPageConfig(pageType: PageType): PageConfig {
  return RESEARCH_PAGES.find((page) => page.type === pageType) ?? RESEARCH_PAGES[0];
}

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  steps: AgentStep[];
  run_id?: string | null;
  source: string;
  created_at: string;
};

export type ThreadSummary = {
  id: string;
  page_type: PageType;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Conversation = {
  thread_id: string;
  page_type: PageType;
  title: string;
  updated_at: string;
  messages: ConversationMessage[];
};
