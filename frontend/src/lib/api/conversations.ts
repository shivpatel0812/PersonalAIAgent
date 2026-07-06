import type { Conversation, PageType } from "../../types/conversation";
import { apiUrl } from "./client";

export async function fetchConversation(pageType: PageType): Promise<Conversation> {
  const response = await fetch(`${apiUrl}/ai/conversations/${pageType}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Failed to load conversation: ${response.status}`);
  }
  return response.json();
}
