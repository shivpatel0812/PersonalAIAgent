import { useCallback, useEffect, useState } from "react";
import { fetchConversation } from "../lib/api/conversations";
import { postResearchStreaming } from "../lib/api/research";
import type { ConversationMessage, PageType } from "../types/conversation";
import type { AgentStep, PastRunMemory, ResearchStatus } from "../types/research";

type UseConversationResult = {
  messages: ConversationMessage[];
  status: ResearchStatus;
  error: string | null;
  streamingSteps: AgentStep[];
  memoryRuns: PastRunMemory[];
  loadingConversation: boolean;
  pendingQuestion: string | null;
  submitMessage: (question: string, maxIterations: number) => Promise<void>;
  reload: () => Promise<void>;
};

export function useConversation(pageType: PageType): UseConversationResult {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState<ResearchStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [streamingSteps, setStreamingSteps] = useState<AgentStep[]>([]);
  const [memoryRuns, setMemoryRuns] = useState<PastRunMemory[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(true);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoadingConversation(true);
    try {
      const conversation = await fetchConversation(pageType);
      setMessages(conversation.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversation");
      setMessages([]);
    } finally {
      setLoadingConversation(false);
    }
  }, [pageType]);

  useEffect(() => {
    setStatus("idle");
    setError(null);
    setStreamingSteps([]);
    setMemoryRuns([]);
    setPendingQuestion(null);
    void reload();
  }, [reload]);

  const submitMessage = useCallback(
    async (question: string, maxIterations: number) => {
      const trimmed = question.trim();
      if (!trimmed) return;

      setPendingQuestion(trimmed);
      setStatus("loading");
      setError(null);
      setStreamingSteps([]);
      setMemoryRuns([]);

      let streamFailed = false;

      try {
        await postResearchStreaming(
          {
            question: trimmed,
            max_iterations: maxIterations,
            page_type: pageType,
          },
          {
            onMemory: (runs) => setMemoryRuns(runs),
            onStep: (event) => {
              if (event.type === "step") {
                setStreamingSteps((prev) => [...prev, event.step]);
              }
            },
            onError: (errorMsg) => {
              streamFailed = true;
              setError(errorMsg);
              setStatus("error");
            },
          }
        );

        if (!streamFailed) {
          await reload();
          setStatus("success");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Research failed");
        setStatus("error");
      } finally {
        setStreamingSteps([]);
        setPendingQuestion(null);
      }
    },
    [pageType, reload]
  );

  return {
    messages,
    status,
    error,
    streamingSteps,
    memoryRuns,
    loadingConversation,
    pendingQuestion,
    submitMessage,
    reload,
  };
}
