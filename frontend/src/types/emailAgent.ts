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

export const PLACEHOLDER_EMAIL_ITEMS: EmailAgentItem[] = [
  {
    id: "placeholder-1",
    senderName: "Todd Richardson",
    senderEmail: "todd.richardson@example.gov",
    subject: "RE: New Entry: Freedom of Information Act Request",
    summary:
      "Todd is following up on your FOIA request from 7/1/2026 and has attached documents for your review. He's asking if you need anything else to move forward.",
    gmailUrl: "https://mail.google.com/mail/u/0/#inbox",
    draftResponse:
      "Hi Todd,\n\nThank you for sending the documents related to my FOIA request. I've received them and will review everything this week.\n\nI'll follow up if I have any questions.\n\nBest,\nShiv",
    status: "draft_ready",
  },
  {
    id: "placeholder-2",
    senderName: "Alex Chen",
    senderEmail: "alex.chen@company.com",
    subject: "Quick sync on project timeline?",
    summary:
      "Alex wants to schedule a call about the project timeline and asked whether you're available Thursday or Friday afternoon.",
    gmailUrl: "https://mail.google.com/mail/u/0/#inbox",
    draftResponse:
      "Hi Alex,\n\nThanks for reaching out. Friday afternoon works better for me — would 2:00 PM ET work on your end?\n\nLooking forward to catching up.\n\nBest,\nShiv",
    status: "draft_ready",
  },
];
