import type { Conversation, PageType, ThreadSummary } from "../../types/conversation";
import { apiUrl } from "./client";

export async function fetchThreads(pageType: PageType): Promise<ThreadSummary[]> {
  const response = await fetch(`${apiUrl}/ai/threads?page_type=${pageType}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to load chats: ${response.status}`);
  }
  return response.json();
}

export async function createThread(
  pageType: PageType,
  title?: string
): Promise<ThreadSummary> {
  const response = await fetch(`${apiUrl}/ai/threads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page_type: pageType, title }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to create chat: ${response.status}`);
  }
  return response.json();
}

export async function fetchThread(threadId: string): Promise<Conversation> {
  const response = await fetch(`${apiUrl}/ai/threads/${threadId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to load chat: ${response.status}`);
  }
  return response.json();
}

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(`${apiUrl}/ai/threads/${threadId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to delete chat: ${response.status}`);
  }
}

/** @deprecated Use fetchThread instead */
export async function fetchConversation(pageType: PageType): Promise<Conversation> {
  const response = await fetch(`${apiUrl}/ai/conversations/${pageType}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to load conversation: ${response.status}`);
  }
  return response.json();
}
