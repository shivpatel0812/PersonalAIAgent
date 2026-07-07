import type { ThreadSummary } from "../../types/conversation";

type ChatSidebarProps = {
  threads: ThreadSummary[];
  activeThreadId: string | null;
  loading: boolean;
  onSelect: (threadId: string) => void;
  onNewChat: () => void;
  onDelete: (threadId: string) => void;
};

function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}

export function ChatSidebar({
  threads,
  activeThreadId,
  loading,
  onSelect,
  onNewChat,
  onDelete,
}: ChatSidebarProps) {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-950/90">
      <div className="border-b border-slate-800 px-3 py-3">
        <button
          type="button"
          onClick={onNewChat}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-accent/50 hover:bg-accent/10"
        >
          + New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {loading && (
          <p className="px-2 py-3 text-xs text-slate-500">Loading chats…</p>
        )}

        {!loading && threads.length === 0 && (
          <p className="px-2 py-3 text-xs leading-5 text-slate-500">
            No chats yet. Start a new one — memory still works across all chats.
          </p>
        )}

        <ul className="space-y-1">
          {threads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            return (
              <li key={thread.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(thread.id)}
                  className={`w-full rounded-lg px-3 py-2.5 pr-8 text-left transition ${
                    isActive
                      ? "bg-accent/10 text-slate-100"
                      : "text-slate-400 hover:bg-slate-900/80 hover:text-slate-200"
                  }`}
                >
                  <p className="truncate text-sm font-medium">{thread.title}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    {formatRelativeTime(thread.updated_at)}
                  </p>
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${thread.title}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(thread.id);
                  }}
                  className="absolute right-2 top-2 rounded px-1.5 py-0.5 text-xs text-slate-600 opacity-0 transition hover:bg-red-500/10 hover:text-red-300 group-hover:opacity-100"
                >
                  ×
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
