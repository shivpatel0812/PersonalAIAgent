import { useCallback, useEffect, useState } from "react";
import { fetchThread } from "../lib/api/conversations";
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
  clearMessages: () => void;
};

export function useConversation(
  pageType: PageType,
  threadId: string | null
): UseConversationResult {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState<ResearchStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [streamingSteps, setStreamingSteps] = useState<AgentStep[]>([]);
  const [memoryRuns, setMemoryRuns] = useState<PastRunMemory[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const reload = useCallback(async () => {
    if (!threadId) {
      setMessages([]);
      setLoadingConversation(false);
      return;
    }

    setLoadingConversation(true);
    try {
      const conversation = await fetchThread(threadId);
      setMessages(conversation.messages);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load conversation");
      setMessages([]);
    } finally {
      setLoadingConversation(false);
    }
  }, [threadId]);

  useEffect(() => {
    setStatus("idle");
    setStreamingSteps([]);
    setMemoryRuns([]);
    setPendingQuestion(null);
    void reload();
  }, [reload, pageType]);

  const submitMessage = useCallback(
    async (question: string, maxIterations: number) => {
      const trimmed = question.trim();
      if (!trimmed || !threadId) return;

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
            thread_id: threadId,
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
    [pageType, reload, threadId]
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
    clearMessages,
  };
}
