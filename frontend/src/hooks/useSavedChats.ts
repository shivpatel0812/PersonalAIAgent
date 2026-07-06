import { useCallback, useEffect, useState } from "react";
import { fetchRun, fetchRuns, runDetailToSavedChat } from "../lib/api/runs";
import {
  deleteSavedChat,
  listSavedChats,
  markSavedChatRunId,
  upsertSavedChat,
} from "../lib/storage/savedChats";
import type { ResearchResponse, SavedChat } from "../types/research";

type UseSavedChatsResult = {
  chats: SavedChat[];
  activeChatId: string | null;
  loading: boolean;
  syncing: boolean;
  saveSession: (result: ResearchResponse) => string;
  markSessionSaved: (localId: string, runId: string) => void;
  selectChat: (chat: SavedChat) => SavedChat;
  loadChatById: (id: string) => Promise<SavedChat | null>;
  removeChat: (id: string) => void;
  refreshFromServer: () => Promise<void>;
  setActiveChatId: (id: string | null) => void;
  startNewChat: () => void;
};

export function useSavedChats(): UseSavedChatsResult {
  const [chats, setChats] = useState<SavedChat[]>(() => listSavedChats());
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const refreshFromServer = useCallback(async () => {
    setSyncing(true);
    try {
      const remoteRuns = await fetchRuns(50);
      const local = listSavedChats();
      const localIds = new Set(local.map((chat) => chat.id));

      for (const run of remoteRuns) {
        if (localIds.has(run.id)) continue;
        if (!run.final_answer) continue;

        try {
          const detail = await fetchRun(run.id);
          const chat = runDetailToSavedChat(detail);
          upsertSavedChat(chat);
          localIds.add(chat.id);
        } catch {
          upsertSavedChat({
            id: run.id,
            question: run.question,
            answer: run.final_answer ?? "",
            steps: [],
            iterations: 0,
            memory_runs: [],
            created_at: run.created_at,
            saved: true,
          });
          localIds.add(run.id);
        }
      }

      setChats(listSavedChats());
    } catch {
      // Keep local chats if server sync fails.
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    void refreshFromServer();
  }, [refreshFromServer]);

  const saveSession = useCallback((result: ResearchResponse) => {
    const id = result.run_id ?? crypto.randomUUID();
    const updated = upsertSavedChat({
      id,
      question: result.question,
      answer: result.answer,
      steps: result.steps,
      iterations: result.iterations,
      memory_runs: result.memory_runs ?? [],
      created_at: new Date().toISOString(),
      saved: result.saved,
    });
    setChats(updated);
    setActiveChatId(id);
    return id;
  }, []);

  const markSessionSaved = useCallback((localId: string, runId: string) => {
    setChats(markSavedChatRunId(localId, runId));
    setActiveChatId(runId);
  }, []);

  const selectChat = useCallback((chat: SavedChat) => {
    setActiveChatId(chat.id);
    return chat;
  }, []);

  const loadChatById = useCallback(async (id: string) => {
    const local = listSavedChats().find((chat) => chat.id === id);
    if (local?.steps.length) {
      setActiveChatId(id);
      return local;
    }

    setLoading(true);
    try {
      const detail = await fetchRun(id);
      const chat = runDetailToSavedChat(detail);
      const updated = upsertSavedChat(chat);
      setChats(updated);
      setActiveChatId(id);
      return chat;
    } catch {
      if (local) {
        setActiveChatId(id);
        return local;
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const removeChat = useCallback((id: string) => {
    setChats(deleteSavedChat(id));
    setActiveChatId((current) => (current === id ? null : current));
  }, []);

  const startNewChat = useCallback(() => {
    setActiveChatId(null);
  }, []);

  return {
    chats,
    activeChatId,
    loading,
    syncing,
    saveSession,
    markSessionSaved,
    selectChat,
    loadChatById,
    removeChat,
    refreshFromServer,
    setActiveChatId,
    startNewChat,
  };
}
