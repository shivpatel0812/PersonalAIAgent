import { apiUrl } from "./client";
import type { FindTurnResponse, ThumbFeedback } from "../../types/find";

export function getFindImageProxyUrl(imageUrl: string): string {
  return `${apiUrl}/find/image-proxy?url=${encodeURIComponent(imageUrl)}`;
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function createFindSession(): Promise<string> {
  const response = await fetch(`${apiUrl}/find/sessions`, { method: "POST" });
  const data = await parseJson<{ session_id: string }>(response);
  return data.session_id;
}

export async function fetchFindSession(sessionId: string): Promise<FindTurnResponse> {
  const response = await fetch(`${apiUrl}/find/sessions/${sessionId}`);
  return parseJson<FindTurnResponse>(response);
}

export async function sendFindMessage(
  sessionId: string,
  message: string,
  feedback?: ThumbFeedback,
): Promise<FindTurnResponse> {
  const response = await fetch(`${apiUrl}/find/sessions/${sessionId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, feedback: feedback ?? null }),
  });
  return parseJson<FindTurnResponse>(response);
}

export async function resetFindSession(sessionId: string): Promise<FindTurnResponse> {
  const response = await fetch(`${apiUrl}/find/sessions/${sessionId}/reset`, {
    method: "POST",
  });
  return parseJson<FindTurnResponse>(response);
}
