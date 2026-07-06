import type { ResearchResponse, SavedChat } from "../../types/research";

const STORAGE_KEY = "research-saved-chats";
const MAX_CHATS = 50;

function loadAll(): SavedChat[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedChat[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(chats: SavedChat[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats.slice(0, MAX_CHATS)));
}

export function listSavedChats(): SavedChat[] {
  return loadAll().sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
}

export function upsertSavedChat(chat: SavedChat): SavedChat[] {
  const chats = loadAll();
  const index = chats.findIndex((item) => item.id === chat.id);
  if (index >= 0) {
    chats[index] = chat;
  } else {
    chats.unshift(chat);
  }
  writeAll(chats);
  return listSavedChats();
}

export function saveResearchSession(
  result: ResearchResponse,
  options?: { durationMs?: number | null }
): SavedChat[] {
  const id = result.run_id ?? crypto.randomUUID();
  const chat: SavedChat = {
    id,
    question: result.question,
    answer: result.answer,
    steps: result.steps,
    iterations: result.iterations,
    memory_runs: result.memory_runs ?? [],
    created_at: new Date().toISOString(),
    saved: result.saved,
  };

  void options;
  return upsertSavedChat(chat);
}

export function markSavedChatRunId(localId: string, runId: string): SavedChat[] {
  const chats = loadAll();
  const index = chats.findIndex((item) => item.id === localId);
  if (index < 0) return listSavedChats();

  const existing = chats[index];
  const withoutDuplicate = chats.filter((item) => item.id !== runId);
  const updatedIndex = withoutDuplicate.findIndex((item) => item.id === localId);
  if (updatedIndex < 0) return listSavedChats();

  withoutDuplicate[updatedIndex] = { ...existing, id: runId, saved: true };
  writeAll(withoutDuplicate);
  return listSavedChats();
}

export function deleteSavedChat(id: string): SavedChat[] {
  writeAll(loadAll().filter((chat) => chat.id !== id));
  return listSavedChats();
}

export function savedChatToResearchResponse(chat: SavedChat): ResearchResponse {
  return {
    run_id: chat.saved ? chat.id : null,
    question: chat.question,
    answer: chat.answer,
    iterations: chat.iterations,
    steps: chat.steps,
    saved: chat.saved,
    memory_runs: chat.memory_runs,
  };
}
