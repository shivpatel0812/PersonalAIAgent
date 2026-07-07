import { useCallback, useEffect, useState } from "react";
import {
  createThread,
  deleteThread as deleteThreadApi,
  fetchThreads,
} from "../lib/api/conversations";
import type { PageType, ThreadSummary } from "../types/conversation";

const storageKey = (pageType: PageType) => `activeThread:${pageType}`;

function readStoredThreadId(pageType: PageType): string | null {
  try {
    return localStorage.getItem(storageKey(pageType));
  } catch {
    return null;
  }
}

function storeThreadId(pageType: PageType, threadId: string | null) {
  try {
    if (threadId) {
      localStorage.setItem(storageKey(pageType), threadId);
    } else {
      localStorage.removeItem(storageKey(pageType));
    }
  } catch {
    // ignore storage errors
  }
}

type UseChatThreadsResult = {
  threads: ThreadSummary[];
  activeThreadId: string | null;
  loadingThreads: boolean;
  error: string | null;
  selectThread: (threadId: string) => void;
  createNewChat: () => Promise<string>;
  removeThread: (threadId: string) => Promise<void>;
  refreshThreads: () => Promise<void>;
};

export function useChatThreads(pageType: PageType): UseChatThreadsResult {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshThreads = useCallback(async () => {
    setLoadingThreads(true);
    try {
      const loaded = await fetchThreads(pageType);
      setThreads(loaded);
      setError(null);

      const storedId = readStoredThreadId(pageType);
      const storedExists = storedId && loaded.some((thread) => thread.id === storedId);
      let nextId = storedExists ? storedId : loaded[0]?.id ?? null;

      if (!nextId) {
        const created = await createThread(pageType);
        setThreads([created]);
        nextId = created.id;
      }

      setActiveThreadId(nextId);
      if (nextId) {
        storeThreadId(pageType, nextId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chats");
      setThreads([]);
      setActiveThreadId(null);
    } finally {
      setLoadingThreads(false);
    }
  }, [pageType]);

  useEffect(() => {
    void refreshThreads();
  }, [refreshThreads]);

  const selectThread = useCallback(
    (threadId: string) => {
      setActiveThreadId(threadId);
      storeThreadId(pageType, threadId);
    },
    [pageType]
  );

  const createNewChat = useCallback(async () => {
    const thread = await createThread(pageType);
    setThreads((prev) => [thread, ...prev.filter((item) => item.id !== thread.id)]);
    setActiveThreadId(thread.id);
    storeThreadId(pageType, thread.id);
    setError(null);
    return thread.id;
  }, [pageType]);

  const removeThread = useCallback(
    async (threadId: string) => {
      await deleteThreadApi(threadId);
      const remaining = threads.filter((thread) => thread.id !== threadId);

      if (remaining.length === 0) {
        const created = await createThread(pageType);
        setThreads([created]);
        setActiveThreadId(created.id);
        storeThreadId(pageType, created.id);
        return;
      }

      setThreads(remaining);
      if (activeThreadId === threadId) {
        const nextId = remaining[0].id;
        setActiveThreadId(nextId);
        storeThreadId(pageType, nextId);
      }
    },
    [activeThreadId, pageType, threads]
  );

  return {
    threads,
    activeThreadId,
    loadingThreads,
    error,
    selectThread,
    createNewChat,
    removeThread,
    refreshThreads,
  };
}
