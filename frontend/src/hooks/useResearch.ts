import { useCallback, useRef, useState } from "react";
import { postResearch, postResearchStreaming } from "../lib/api";
import { savedChatToResearchResponse } from "../lib/storage/savedChats";
import type {
  ResearchResponse,
  ResearchStatus,
  AgentStep,
  PastRunMemory,
  SavedChat,
  StreamEventComplete,
} from "../types/research";

type UseResearchOptions = {
  onSessionComplete?: (result: ResearchResponse) => string | void;
  onSessionSaved?: (localId: string, runId: string) => void;
};

type UseResearchResult = {
  status: ResearchStatus;
  result: ResearchResponse | null;
  error: string | null;
  durationMs: number | null;
  streamingSteps: AgentStep[];
  memoryRuns: PastRunMemory[];
  submitQuestion: (question: string, maxIterations: number) => Promise<void>;
  submitQuestionStreaming: (question: string, maxIterations: number) => Promise<void>;
  loadSession: (chat: SavedChat) => void;
  reset: () => void;
};

export function useResearch(options: UseResearchOptions = {}): UseResearchResult {
  const [status, setStatus] = useState<ResearchStatus>("idle");
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [streamingSteps, setStreamingSteps] = useState<AgentStep[]>([]);
  const [memoryRuns, setMemoryRuns] = useState<PastRunMemory[]>([]);
  const pendingLocalIdRef = useRef<string | null>(null);

  const loadSession = useCallback((chat: SavedChat) => {
    const response = savedChatToResearchResponse(chat);
    setStatus("success");
    setError(null);
    setResult(response);
    setDurationMs(null);
    setStreamingSteps(chat.steps);
    setMemoryRuns(chat.memory_runs);
  }, []);

  const handleSessionComplete = useCallback(
    (response: ResearchResponse) => {
      const localId = options.onSessionComplete?.(response);
      if (typeof localId === "string") {
        pendingLocalIdRef.current = localId;
      }
    },
    [options]
  );

  const submitQuestion = useCallback(async (question: string, maxIterations: number) => {
    const trimmed = question.trim();
    if (!trimmed) return;

    setStatus("loading");
    setError(null);
    setResult(null);
    setDurationMs(null);
    setMemoryRuns([]);

    const startedAt = performance.now();

    try {
      const response = await postResearch({
        question: trimmed,
        max_iterations: maxIterations,
      });
      setResult(response);
      setMemoryRuns(response.memory_runs ?? []);
      setDurationMs(Math.round(performance.now() - startedAt));
      setStatus("success");
      handleSessionComplete(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research failed");
      setDurationMs(Math.round(performance.now() - startedAt));
      setStatus("error");
    }
  }, [handleSessionComplete]);

  const submitQuestionStreaming = useCallback(
    async (question: string, maxIterations: number) => {
      const trimmed = question.trim();
      if (!trimmed) return;

      setStatus("loading");
      setError(null);
      setResult(null);
      setDurationMs(null);
      setStreamingSteps([]);
      setMemoryRuns([]);

      const startedAt = performance.now();

      try {
        await postResearchStreaming(
          {
            question: trimmed,
            max_iterations: maxIterations,
          },
          {
            onMemory: (runs) => {
              setMemoryRuns(runs);
            },
            onStep: (event) => {
              if (event.type === "step") {
                setStreamingSteps((prev) => [...prev, event.step]);
              }
            },
            onComplete: (event) => {
              if (event.type === "complete") {
                const completeEvent = event as StreamEventComplete;
                const response: ResearchResponse = {
                  run_id: null,
                  question: completeEvent.question,
                  answer: completeEvent.answer,
                  iterations: completeEvent.iterations,
                  steps: completeEvent.steps,
                  saved: false,
                  memory_runs: completeEvent.memory_runs ?? [],
                };
                setResult(response);
                setDurationMs(Math.round(performance.now() - startedAt));
                setStatus("success");
                handleSessionComplete(response);
              }
            },
            onError: (errorMsg) => {
              setError(errorMsg);
              setDurationMs(Math.round(performance.now() - startedAt));
              setStatus("error");
            },
            onSaved: (runId) => {
              setResult((prev) => {
                if (!prev) return null;
                const updated = { ...prev, run_id: runId, saved: true };
                if (pendingLocalIdRef.current) {
                  options.onSessionSaved?.(pendingLocalIdRef.current, runId);
                  pendingLocalIdRef.current = null;
                } else {
                  handleSessionComplete(updated);
                }
                return updated;
              });
            },
          }
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Research failed");
        setDurationMs(Math.round(performance.now() - startedAt));
        setStatus("error");
      }
    },
    [handleSessionComplete, options]
  );

  const reset = useCallback(() => {
    setStatus("idle");
    setResult(null);
    setError(null);
    setDurationMs(null);
    setStreamingSteps([]);
    setMemoryRuns([]);
    pendingLocalIdRef.current = null;
  }, []);

  return {
    status,
    result,
    error,
    durationMs,
    streamingSteps,
    memoryRuns,
    submitQuestion,
    submitQuestionStreaming,
    loadSession,
    reset,
  };
}
