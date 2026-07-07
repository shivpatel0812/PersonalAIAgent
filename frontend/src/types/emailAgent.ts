export type EmailAgentStatus = "needs_draft" | "draft_ready" | "waiting_on_you";

export type EmailAgentItem = {
  id: string;
  senderName: string;
  senderEmail: string;
  subject: string;
  summary: string;
  gmailUrl: string;
  draftResponse: string;
  status: EmailAgentStatus;
};

export type DraftChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};
