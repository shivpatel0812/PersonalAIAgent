import { useMemo, useState } from "react";
import {
  PLACEHOLDER_EMAIL_ITEMS,
  type DraftChatMessage,
  type EmailAgentItem,
} from "../../types/emailAgent";

const STATUS_LABELS = {
  needs_draft: "Drafting…",
  draft_ready: "Ready for review",
  waiting_on_you: "Needs your input",
} as const;

function buildInitialChat(item: EmailAgentItem): DraftChatMessage[] {
  return [
    {
      id: `${item.id}-welcome`,
      role: "assistant",
      content:
        "I've drafted a reply based on the email thread. Tell me what to change — tone, length, or details to add — and I'll update the response below. Nothing sends until you approve.",
    },
  ];
}

export function EmailAgentPanel() {
  const [items] = useState<EmailAgentItem[]>(PLACEHOLDER_EMAIL_ITEMS);
  const [selectedId, setSelectedId] = useState(items[0]?.id ?? "");
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
    Object.fromEntries(items.map((item) => [item.id, item.draftResponse]))
  );
  const [chatByEmail, setChatByEmail] = useState<Record<string, DraftChatMessage[]>>(() =>
    Object.fromEntries(items.map((item) => [item.id, buildInitialChat(item)]))
  );
  const [chatInput, setChatInput] = useState("");
  const [adjusting, setAdjusting] = useState(false);
  const [approvedId, setApprovedId] = useState<string | null>(null);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0],
    [items, selectedId]
  );

  const chatMessages = selected ? chatByEmail[selected.id] ?? [] : [];

  function handleAdjustDraft() {
    if (!selected || !chatInput.trim()) return;

    const userMessage: DraftChatMessage = {
      id: `${selected.id}-user-${Date.now()}`,
      role: "user",
      content: chatInput.trim(),
    };

    setChatByEmail((prev) => ({
      ...prev,
      [selected.id]: [...(prev[selected.id] ?? []), userMessage],
    }));
    setChatInput("");
    setAdjusting(true);

  // Simulate backend revision until API is wired
    window.setTimeout(() => {
      const note =
        "I've updated the draft with your feedback. Review the response on the left — approve when you're happy, or keep refining here.";

      setDrafts((prev) => ({
        ...prev,
        [selected.id]: `${prev[selected.id]}\n\n[Updated per your note: "${userMessage.content}"]`,
      }));

      setChatByEmail((prev) => ({
        ...prev,
        [selected.id]: [
          ...(prev[selected.id] ?? []),
          {
            id: `${selected.id}-assistant-${Date.now()}`,
            role: "assistant",
            content: note,
          },
        ],
      }));
      setAdjusting(false);
    }, 700);
  }

  function handleApprove() {
    if (!selected) return;
    setApprovedId(selected.id);
    setChatByEmail((prev) => ({
      ...prev,
      [selected.id]: [
        ...(prev[selected.id] ?? []),
        {
          id: `${selected.id}-approved-${Date.now()}`,
          role: "assistant",
          content:
            "Approved locally (placeholder). Sending will be enabled once the backend is connected — no email has been sent.",
        },
      ],
    }));
  }

  if (items.length === 0) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-8 text-center">
        <p className="text-sm font-medium text-slate-200">Email Agent</p>
        <p className="mt-2 text-sm text-slate-500">
          No emails need a response right now. When the backend is connected, messages that
          need a reply will show up here.
        </p>
      </section>
    );
  }

  return (
    <section className="flex min-h-[32rem] flex-col rounded-xl border border-slate-800 bg-slate-900/30">
      <div className="border-b border-slate-800 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-200">Email Agent</p>
            <p className="text-xs text-slate-500">
              Responses need your approval before anything is sent
            </p>
          </div>
          <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-300">
            {items.length} need a response
          </span>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Queue */}
        <aside className="border-b border-slate-800 lg:w-56 lg:shrink-0 lg:border-b-0 lg:border-r">
          <p className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Inbox
          </p>
          <div className="space-y-1 px-2 pb-3">
            {items.map((item) => {
              const isActive = item.id === selected?.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full rounded-lg px-3 py-2.5 text-left transition ${
                    isActive
                      ? "border border-accent/40 bg-accent/10"
                      : "border border-transparent hover:bg-slate-800/60"
                  }`}
                >
                  <p className="truncate text-sm font-medium text-slate-200">
                    {item.senderName}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">{item.subject}</p>
                  <p className="mt-1 text-[10px] text-slate-600">
                    {STATUS_LABELS[item.status]}
                  </p>
                </button>
              );
            })}
          </div>
        </aside>

        {selected && (
          <>
            {/* Email summary + draft */}
            <div className="flex min-w-0 flex-1 flex-col border-b border-slate-800 lg:border-b-0 lg:border-r">
              <div className="flex-1 space-y-4 overflow-y-auto p-4">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium text-slate-100">{selected.senderName}</p>
                      <p className="text-xs text-slate-500">{selected.senderEmail}</p>
                    </div>
                    <a
                      href={selected.gmailUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-accent hover:underline"
                    >
                      View in Gmail →
                    </a>
                  </div>
                  <p className="text-sm font-medium text-slate-300">{selected.subject}</p>
                  <p className="mt-3 text-sm leading-6 text-slate-400">{selected.summary}</p>
                </div>

                <div>
                  <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    Draft response
                  </p>
                  <textarea
                    value={drafts[selected.id] ?? ""}
                    onChange={(event) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [selected.id]: event.target.value,
                      }))
                    }
                    rows={10}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm leading-6 text-slate-200 outline-none focus:border-accent/50"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-2 border-t border-slate-800 p-4">
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={approvedId === selected.id}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {approvedId === selected.id ? "Approved (placeholder)" : "Approve & send"}
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:text-slate-100"
                >
                  Discard
                </button>
              </div>
            </div>

            {/* Adjustment chat */}
            <div className="flex w-full flex-col lg:w-80 xl:w-96">
              <p className="border-b border-slate-800 px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Adjust draft
              </p>
              <div className="flex-1 space-y-3 overflow-y-auto p-4">
                {chatMessages.map((message) => (
                  <div
                    key={message.id}
                    className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
                  >
                    <div
                      className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-6 ${
                        message.role === "user"
                          ? "rounded-br-md border border-accent/30 bg-accent/10 text-slate-100"
                          : "rounded-bl-md border border-slate-800 bg-slate-950/80 text-slate-300"
                      }`}
                    >
                      {message.content}
                    </div>
                  </div>
                ))}
                {adjusting && (
                  <p className="text-xs text-slate-500">Updating draft…</p>
                )}
              </div>
              <div className="border-t border-slate-800 p-3">
                <div className="flex items-end gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2">
                  <textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey && !adjusting) {
                        event.preventDefault();
                        handleAdjustDraft();
                      }
                    }}
                    placeholder="e.g. Make it shorter, mention Friday works…"
                    rows={2}
                    disabled={adjusting}
                    className="min-h-[2.5rem] flex-1 resize-none bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600"
                  />
                  <button
                    type="button"
                    onClick={handleAdjustDraft}
                    disabled={adjusting || !chatInput.trim()}
                    className="rounded-full bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-40"
                  >
                    →
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
