import type { ResearchResponse, StreamEvent, PastRunMemory } from "../../types/research";
import { apiUrl } from "./client";

export type ResearchRequest = {
  question: string;
  max_iterations: number;
  page_type?: string;
  thread_id?: string;
};

export async function postResearch(body: ResearchRequest): Promise<ResearchResponse> {
  const response = await fetch(`${apiUrl}/ai/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Research failed: ${response.status}`);
  }

  return response.json();
}

export type StreamCallbacks = {
  onStep?: (step: StreamEvent) => void;
  onMemory?: (runs: PastRunMemory[]) => void;
  onComplete?: (event: StreamEvent) => void;
  onError?: (error: string) => void;
  onSaved?: (runId: string) => void;
};

export async function postResearchStreaming(
  body: ResearchRequest,
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`${apiUrl}/ai/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Research failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Response body is null");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Split by double newlines (SSE message separator)
      const messages = buffer.split("\n\n");
      // Keep the last incomplete message in the buffer
      buffer = messages.pop() || "";

      for (const message of messages) {
        if (!message.trim()) continue;

        // Parse SSE format: "event: <type>\ndata: <json>"
        const lines = message.split("\n");
        let eventType = "";
        let eventData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith("data: ")) {
            eventData = line.substring(6).trim();
          }
        }

        if (!eventType || !eventData) continue;

        try {
          const event = JSON.parse(eventData) as StreamEvent;

          if (event.type === "step" && callbacks.onStep) {
            callbacks.onStep(event);
          } else if (event.type === "memory" && callbacks.onMemory) {
            callbacks.onMemory(event.runs);
          } else if (event.type === "complete" && callbacks.onComplete) {
            callbacks.onComplete(event);
          } else if (event.type === "error" && callbacks.onError) {
            callbacks.onError(event.error);
          } else if (event.type === "saved" && callbacks.onSaved) {
            callbacks.onSaved(event.run_id);
          }
        } catch (err) {
          console.error("Failed to parse SSE event:", err, eventData);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
