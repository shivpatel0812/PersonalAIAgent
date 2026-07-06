import type { SavedChat } from "../../types/research";
import { formatMemoryDate } from "../../lib/utils/research";

type HistorySidebarProps = {
  chats: SavedChat[];
  activeChatId: string | null;
  loading: boolean;
  syncing: boolean;
  onSelect: (chat: SavedChat) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onRefresh: () => void;
};

function previewText(chat: SavedChat): string {
  return chat.answer.replace(/\s+/g, " ").trim();
}

export function HistorySidebar({
  chats,
  activeChatId,
  loading,
  syncing,
  onSelect,
  onNewChat,
  onDelete,
  onRefresh,
}: HistorySidebarProps) {
  return (
    <aside className="fixed left-0 top-0 z-20 flex h-screen w-72 flex-col border-r border-slate-800 bg-slate-950/95 backdrop-blur">
      <div className="border-b border-slate-800 px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-medium text-slate-200">Research history</p>
          <button
            type="button"
            onClick={onRefresh}
            disabled={syncing}
            className="text-xs text-slate-500 transition hover:text-slate-300 disabled:opacity-50"
          >
            {syncing ? "Syncing…" : "Sync"}
          </button>
        </div>
        <button
          type="button"
          onClick={onNewChat}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition hover:border-accent hover:text-white"
        >
          + New research
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {loading && (
          <p className="px-2 py-3 text-xs text-slate-500">Loading session…</p>
        )}

        {!loading && chats.length === 0 && (
          <p className="px-2 py-3 text-xs leading-6 text-slate-500">
            Completed research sessions will appear here.
          </p>
        )}

        <div className="space-y-2">
          {chats.map((chat) => {
            const isActive = chat.id === activeChatId;
            return (
              <div
                key={chat.id}
                className={`group rounded-xl border px-3 py-3 transition ${
                  isActive
                    ? "border-accent/50 bg-accent/10"
                    : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(chat)}
                  className="w-full text-left"
                >
                  <p className="mb-1 line-clamp-2 text-sm font-medium text-slate-200">
                    {chat.question}
                  </p>
                  <p className="mb-2 line-clamp-2 text-xs leading-5 text-slate-500">
                    {previewText(chat) || "No answer saved"}
                  </p>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span>{formatMemoryDate(chat.created_at)}</span>
                    {chat.saved && <span>· Saved</span>}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(chat.id)}
                  className="mt-2 text-[11px] text-slate-600 opacity-0 transition group-hover:opacity-100 hover:text-red-400"
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
