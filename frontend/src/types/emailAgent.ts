export type EmailAgentStatus = "needs_draft" | "draft_ready" | "waiting_on_you" | "listed";

export type EmailAgentItem = {
  id: string;
  senderName: string;
  senderEmail: string;
  subject: string;
  summary: string;
  gmailUrl: string;
  mailUrl?: string;
  mailProvider?: "google" | "microsoft";
  draftResponse: string;
  status: EmailAgentStatus;
  needsResponse?: boolean;
  alwaysUrgent?: boolean;
  schedulingDetected?: boolean;
  calendarChecked?: boolean;
  calendarConnected?: boolean;
};

export type DraftChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type EmailThreadAttachment = {
  filename: string;
  mimeType: string;
  size: number;
  extractedTextPreview?: string | null;
  extractNote?: string | null;
};

export type EmailThreadMessage = {
  id: string;
  fromEmail: string;
  toEmail: string | null;
  date: string;
  subject: string;
  body: string;
  isInbound: boolean;
  isTarget: boolean;
  attachments?: EmailThreadAttachment[];
};

export type EmailThreadDetail = {
  threadId: string;
  subject: string;
  messages: EmailThreadMessage[];
};
