import type { DraftChatMessage, EmailAgentItem, EmailThreadDetail } from "../../types/emailAgent";
import { apiUrl } from "./client";

export type EmailAgentItemDetail = {
  item: EmailAgentItem;
  chatMessages: DraftChatMessage[];
};

export type EmailAgentScanResult = {
  status: string;
  scanned?: number;
  queued?: number;
  drafted?: number;
  reason?: string;
};

async function parseError(response: Response, fallback: string): Promise<never> {
  const detail = await response.text();
  throw new Error(detail || `${fallback}: ${response.status}`);
}

export async function fetchEmailAgentItems(): Promise<EmailAgentItem[]> {
  const response = await fetch(`${apiUrl}/email-agent/items`);
  if (!response.ok) {
    await parseError(response, "Failed to load email queue");
  }
  const data = await response.json();
  return data.items ?? [];
}

export async function fetchEmailAgentItem(itemId: string): Promise<EmailAgentItemDetail> {
  const response = await fetch(`${apiUrl}/email-agent/items/${itemId}`);
  if (!response.ok) {
    await parseError(response, "Failed to load email");
  }
  return response.json();
}

export async function fetchEmailAgentThread(itemId: string): Promise<EmailThreadDetail> {
  const response = await fetch(`${apiUrl}/email-agent/items/${itemId}/thread`);
  if (!response.ok) {
    await parseError(response, "Failed to load full email");
  }
  return response.json();
}

export async function scanEmailAgentInbox(): Promise<EmailAgentScanResult> {
  const response = await fetch(`${apiUrl}/email-agent/scan`, { method: "POST" });
  if (!response.ok) {
    await parseError(response, "Inbox scan failed");
  }
  return response.json();
}

export async function adjustEmailDraft(
  itemId: string,
  message: string
): Promise<{ draftResponse: string; assistantMessage: DraftChatMessage }> {
  const response = await fetch(`${apiUrl}/email-agent/items/${itemId}/adjust`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    await parseError(response, "Failed to adjust draft");
  }
  return response.json();
}

export async function approveEmailDraft(
  itemId: string,
  draftResponse: string
): Promise<{ success: boolean; messageId?: string }> {
  const response = await fetch(`${apiUrl}/email-agent/items/${itemId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draftResponse }),
  });
  if (!response.ok) {
    await parseError(response, "Failed to send email");
  }
  return response.json();
}

export async function discardEmailItem(itemId: string): Promise<void> {
  const response = await fetch(`${apiUrl}/email-agent/items/${itemId}/discard`, {
    method: "POST",
  });
  if (!response.ok) {
    await parseError(response, "Failed to discard email");
  }
}
