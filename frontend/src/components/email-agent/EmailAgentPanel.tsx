import { useCallback, useEffect, useMemo, useState } from "react";
import { GoogleAccountsBar } from "../integrations/GoogleAccountsBar";
import { MicrosoftAccountsBar } from "../integrations/MicrosoftAccountsBar";
import {
  adjustEmailDraft,
  approveEmailDraft,
  discardEmailItem,
  fetchEmailAgentItem,
  fetchEmailAgentItems,
  fetchEmailAgentThread,
  scanEmailAgentInbox,
} from "../../lib/api/emailAgent";
import {
  fetchUserEmailProfile,
  saveUserEmailProfile,
} from "../../lib/api/userProfile";
import type {
  DraftChatMessage,
  EmailAgentItem,
  EmailThreadAttachment,
  EmailThreadDetail,
} from "../../types/emailAgent";
import type { UserEmailProfile } from "../../types/userProfile";

const STATUS_LABELS = {
  needs_draft: "Drafting…",
  draft_ready: "Ready for review",
  waiting_on_you: "Needs your input",
} as const;

type EmailAgentPanelProps = {
  googleRefreshKey?: number;
  googleOauthReturn?: "connected" | "error" | null;
  googleOauthError?: string | null;
  microsoftRefreshKey?: number;
  microsoftOauthReturn?: "connected" | "error" | null;
  microsoftOauthError?: string | null;
  onQueueCountChange?: (count: number) => void;
};

export function EmailAgentPanel({
  googleRefreshKey = 0,
  googleOauthReturn = null,
  googleOauthError = null,
  microsoftRefreshKey = 0,
  microsoftOauthReturn = null,
  microsoftOauthError = null,
  onQueueCountChange,
}: EmailAgentPanelProps) {
  const [items, setItems] = useState<EmailAgentItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [chatByEmail, setChatByEmail] = useState<Record<string, DraftChatMessage[]>>({});
  const [chatInput, setChatInput] = useState("");
  const [adjusting, setAdjusting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIncoming, setExpandedIncoming] = useState<Record<string, boolean>>({});
  const [threadByItem, setThreadByItem] = useState<Record<string, EmailThreadDetail>>({});
  const [expandedPdfPreview, setExpandedPdfPreview] = useState<Record<string, boolean>>({});
  const [loadingThreadFor, setLoadingThreadFor] = useState<string | null>(null);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [profile, setProfile] = useState<UserEmailProfile | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  function formatAttachmentSize(size: number): string {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function togglePdfPreview(messageId: string, filename: string) {
    const key = `${messageId}:${filename}`;
    setExpandedPdfPreview((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0],
    [items, selectedId]
  );

  const chatMessages = selected ? chatByEmail[selected.id] ?? [] : [];

  const loadItemDetail = useCallback(async (itemId: string) => {
    const detail = await fetchEmailAgentItem(itemId);
    setDrafts((prev) => ({ ...prev, [itemId]: detail.item.draftResponse }));
    setChatByEmail((prev) => ({ ...prev, [itemId]: detail.chatMessages }));
    setItems((prev) =>
      prev.map((item) => (item.id === itemId ? { ...item, ...detail.item } : item))
    );
  }, []);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const queue = await fetchEmailAgentItems();
      setItems(queue);
      onQueueCountChange?.(queue.length);
      if (queue.length > 0) {
        const firstId = queue[0].id;
        setSelectedId((current) => current || firstId);
        setDrafts(Object.fromEntries(queue.map((item) => [item.id, item.draftResponse])));
        await loadItemDetail(queue[0].id);
      } else {
        setSelectedId("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load email queue");
    } finally {
      setLoading(false);
    }
  }, [loadItemDetail, onQueueCountChange]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    void fetchUserEmailProfile()
      .then(setProfile)
      .catch(() => undefined);
  }, []);

  async function handleSaveProfile() {
    if (!profile) return;
    setSavingProfile(true);
    setProfileSaved(false);
    setError(null);
    try {
      const saved = await saveUserEmailProfile({
        displayName: profile.displayName,
        roleTitle: profile.roleTitle,
        communicationStyle: profile.communicationStyle,
        defaultSignOff: profile.defaultSignOff,
        expertiseAreas: profile.expertiseAreas,
        timezone: profile.timezone,
      });
      setProfile(saved);
      setProfileSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save reply preferences");
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleSelectItem(itemId: string) {
    setSelectedId(itemId);
    if (!chatByEmail[itemId]) {
      try {
        await loadItemDetail(itemId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load email");
      }
    }
  }

  async function toggleIncomingEmail(itemId: string) {
    const isExpanded = expandedIncoming[itemId];
    if (isExpanded) {
      setExpandedIncoming((prev) => ({ ...prev, [itemId]: false }));
      return;
    }

    setExpandedIncoming((prev) => ({ ...prev, [itemId]: true }));

    if (threadByItem[itemId]) return;

    setLoadingThreadFor(itemId);
    setError(null);
    try {
      const thread = await fetchEmailAgentThread(itemId);
      setThreadByItem((prev) => ({ ...prev, [itemId]: thread }));
    } catch (err) {
      setExpandedIncoming((prev) => ({ ...prev, [itemId]: false }));
      setError(err instanceof Error ? err.message : "Failed to load full email");
    } finally {
      setLoadingThreadFor(null);
    }
  }

  async function handleScan() {
    setScanning(true);
    setError(null);
    try {
      await scanEmailAgentInbox();
      await loadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }

  async function handleAdjustDraft() {
    if (!selected || !chatInput.trim()) return;

    const message = chatInput.trim();
    setChatInput("");
    setAdjusting(true);
    setError(null);

    const userMessage: DraftChatMessage = {
      id: `${selected.id}-user-${Date.now()}`,
      role: "user",
      content: message,
    };
    setChatByEmail((prev) => ({
      ...prev,
      [selected.id]: [...(prev[selected.id] ?? []), userMessage],
    }));

    try {
      const result = await adjustEmailDraft(selected.id, message);
      setDrafts((prev) => ({ ...prev, [selected.id]: result.draftResponse }));
      setChatByEmail((prev) => ({
        ...prev,
        [selected.id]: [...(prev[selected.id] ?? []), result.assistantMessage],
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to adjust draft");
    } finally {
      setAdjusting(false);
    }
  }

  async function handleApprove() {
    if (!selected) return;

    setSending(true);
    setError(null);
    try {
      await approveEmailDraft(selected.id, drafts[selected.id] ?? selected.draftResponse);
      const remaining = items.filter((item) => item.id !== selected.id);
      setItems(remaining);
      onQueueCountChange?.(remaining.length);
      setSelectedId(remaining[0]?.id ?? "");
      if (remaining[0]) {
        await loadItemDetail(remaining[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send email");
    } finally {
      setSending(false);
    }
  }

  async function handleDiscard() {
    if (!selected) return;

    setError(null);
    try {
      await discardEmailItem(selected.id);
      const remaining = items.filter((item) => item.id !== selected.id);
      setItems(remaining);
      onQueueCountChange?.(remaining.length);
      setSelectedId(remaining[0]?.id ?? "");
      if (remaining[0]) {
        await loadItemDetail(remaining[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to discard email");
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <GoogleAccountsBar
        refreshKey={googleRefreshKey}
        oauthReturn={googleOauthReturn}
        oauthErrorMessage={googleOauthError}
      />
      <MicrosoftAccountsBar
        refreshKey={microsoftRefreshKey}
        oauthReturn={microsoftOauthReturn}
        oauthErrorMessage={microsoftOauthError}
      />

      <div className="border-b border-slate-800 px-4 py-2">
        <button
          type="button"
          onClick={() => setPrefsOpen((open) => !open)}
          className="text-xs text-slate-400 transition hover:text-slate-200"
        >
          {prefsOpen ? "Hide reply preferences" : "Reply preferences"}
        </button>
        {prefsOpen && profile && (
          <div className="mt-3 grid gap-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4 md:grid-cols-2">
            <label className="block text-xs text-slate-500">
              Display name
              <input
                value={profile.displayName}
                onChange={(e) =>
                  setProfile({ ...profile, displayName: e.target.value })
                }
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-slate-700"
              />
            </label>
            <label className="block text-xs text-slate-500">
              Role / title
              <input
                value={profile.roleTitle}
                onChange={(e) =>
                  setProfile({ ...profile, roleTitle: e.target.value })
                }
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-slate-700"
              />
            </label>
            <label className="block text-xs text-slate-500 md:col-span-2">
              Communication style
              <textarea
                value={profile.communicationStyle}
                onChange={(e) =>
                  setProfile({ ...profile, communicationStyle: e.target.value })
                }
                rows={2}
                placeholder="e.g. concise and direct, warm and casual"
                className="mt-1 w-full resize-none rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-slate-700"
              />
            </label>
            <label className="block text-xs text-slate-500">
              Default sign-off
              <input
                value={profile.defaultSignOff}
                onChange={(e) =>
                  setProfile({ ...profile, defaultSignOff: e.target.value })
                }
                placeholder="Best, Shiv"
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-slate-700"
              />
            </label>
            <label className="block text-xs text-slate-500">
              Expertise areas (comma-separated)
              <input
                value={profile.expertiseAreas.join(", ")}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    expertiseAreas: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="FOIA, real estate, software"
                className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none focus:border-slate-700"
              />
            </label>
            <div className="flex items-center gap-3 md:col-span-2">
              <button
                type="button"
                onClick={() => void handleSaveProfile()}
                disabled={savingProfile}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-600 disabled:opacity-50"
              >
                {savingProfile ? "Saving…" : "Save preferences"}
              </button>
              {profileSaved && (
                <span className="text-xs text-emerald-400">Saved</span>
              )}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2">
          <p className="text-xs text-red-300">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-slate-400">Loading email queue…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-sm text-slate-400">No emails need a response right now.</p>
          <button
            type="button"
            onClick={() => void handleScan()}
            disabled={scanning}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:border-slate-600 disabled:opacity-50"
          >
            {scanning ? "Scanning inbox…" : "Scan inbox"}
          </button>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          {/* Inbox */}
          <aside className="w-56 shrink-0 overflow-y-auto border-r border-slate-800 bg-slate-950/40">
            <div className="flex items-center justify-between px-4 py-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                Inbox
              </p>
              <button
                type="button"
                onClick={() => void handleScan()}
                disabled={scanning}
                className="text-[10px] text-slate-500 transition hover:text-slate-300 disabled:opacity-50"
              >
                {scanning ? "…" : "↻"}
              </button>
            </div>
            <div className="space-y-1 px-2 pb-4">
              {items.map((item) => {
                const isActive = item.id === selected?.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => void handleSelectItem(item.id)}
                    className={`w-full rounded-lg px-3 py-3 text-left transition ${
                      isActive
                        ? "border border-slate-700 bg-slate-900"
                        : "border border-transparent hover:bg-slate-900/50"
                    }`}
                  >
                    <p className="truncate text-sm font-medium text-slate-100">
                      {item.senderName}
                      {item.alwaysUrgent && (
                        <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-red-400" title="Always urgent sender" />
                      )}
                    </p>
                    <p className="mt-1 truncate text-xs text-slate-500">{item.subject}</p>
                    <p className="mt-2 flex items-center gap-2 text-[10px] text-slate-600">
                      <span>{STATUS_LABELS[item.status]}</span>
                      {item.mailProvider === "microsoft" && (
                        <span className="rounded border border-sky-500/20 px-1 py-0.5 text-[9px] uppercase text-sky-400">
                          Outlook
                        </span>
                      )}
                    </p>
                  </button>
                );
              })}
            </div>
          </aside>

          {selected && (
            <>
              {/* Draft review */}
              <div className="flex min-w-0 flex-1 flex-col border-r border-slate-800">
                <div className="flex-1 overflow-y-auto px-6 py-5">
                  <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-slate-100">
                        {selected.senderName}{" "}
                        <span className="font-normal text-slate-500">
                          {selected.senderEmail}
                        </span>
                      </p>
                    </div>
                    <a
                      href={selected.mailUrl ?? selected.gmailUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-slate-400 transition hover:text-slate-200"
                    >
                      {selected.mailProvider === "microsoft"
                        ? "View in Outlook →"
                        : "View in Gmail →"}
                    </a>
                  </div>

                  <p className="text-sm font-semibold text-slate-200">{selected.subject}</p>

                  <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
                    <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                      Incoming email
                    </p>
                    <p
                      className={`mt-2 text-sm leading-7 text-slate-400 ${
                        expandedIncoming[selected.id] ? "" : "line-clamp-3"
                      }`}
                    >
                      {selected.summary || "No summary available."}
                    </p>

                    {expandedIncoming[selected.id] && (
                      <div className="mt-4 space-y-3 border-t border-slate-800 pt-4">
                        {loadingThreadFor === selected.id && (
                          <p className="text-sm text-slate-500">Loading full thread…</p>
                        )}
                        {threadByItem[selected.id]?.messages.map((message) => (
                          <div
                            key={message.id}
                            className={`rounded-lg border px-3 py-3 ${
                              message.isTarget
                                ? "border-accent/30 bg-accent/5"
                                : "border-slate-800 bg-slate-900/50"
                            }`}
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-medium text-slate-300">
                                {message.fromEmail}
                              </p>
                              <p className="text-[10px] text-slate-600">{message.date}</p>
                            </div>
                            {message.isTarget && (
                              <p className="mt-1 text-[10px] font-medium uppercase tracking-wider text-accent/80">
                                Replying to this message
                              </p>
                            )}
                            <pre className="mt-2 whitespace-pre-wrap font-sans text-sm leading-6 text-slate-300">
                              {message.body}
                            </pre>
                            {message.attachments && message.attachments.length > 0 && (
                              <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                                  Attachments
                                </p>
                                <div className="flex flex-wrap gap-2">
                                  {message.attachments.map((attachment: EmailThreadAttachment) => (
                                    <span
                                      key={`${message.id}-${attachment.filename}`}
                                      className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1 text-[11px] text-slate-400"
                                    >
                                      {attachment.filename} ({formatAttachmentSize(attachment.size)})
                                    </span>
                                  ))}
                                </div>
                                {message.attachments.map((attachment: EmailThreadAttachment) => {
                                  if (!attachment.extractedTextPreview && !attachment.extractNote) {
                                    return null;
                                  }
                                  const previewKey = `${message.id}:${attachment.filename}`;
                                  const isOpen = expandedPdfPreview[previewKey];
                                  return (
                                    <div
                                      key={`${message.id}-${attachment.filename}-preview`}
                                      className="rounded-lg border border-slate-800 bg-slate-950/80"
                                    >
                                      <button
                                        type="button"
                                        onClick={() => togglePdfPreview(message.id, attachment.filename)}
                                        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs text-slate-400 transition hover:text-slate-200"
                                      >
                                        <span>
                                          {attachment.extractedTextPreview
                                            ? `PDF preview: ${attachment.filename}`
                                            : attachment.extractNote}
                                        </span>
                                        {attachment.extractedTextPreview && (
                                          <span>{isOpen ? "Hide" : "Show"}</span>
                                        )}
                                      </button>
                                      {isOpen && attachment.extractedTextPreview && (
                                        <pre className="max-h-48 overflow-y-auto border-t border-slate-800 px-3 py-2 whitespace-pre-wrap font-sans text-xs leading-5 text-slate-400">
                                          {attachment.extractedTextPreview}
                                        </pre>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => void toggleIncomingEmail(selected.id)}
                      disabled={loadingThreadFor === selected.id}
                      className="mt-3 text-xs text-accent transition hover:text-accent/80 disabled:opacity-50"
                    >
                      {loadingThreadFor === selected.id
                        ? "Loading…"
                        : expandedIncoming[selected.id]
                          ? "Show summary only"
                          : "Show full email"}
                    </button>
                  </div>

                  <p className="mb-2 mt-8 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    Draft response
                  </p>
                  {selected.schedulingDetected && (
                    <p className="mb-2 text-xs text-slate-500">
                      {selected.calendarChecked
                        ? "Calendar checked for scheduling"
                        : selected.calendarConnected === false
                          ? "Connect Google Calendar for availability when scheduling"
                          : "Scheduling detected"}
                    </p>
                  )}
                  <textarea
                    value={drafts[selected.id] ?? ""}
                    onChange={(event) =>
                      setDrafts((prev) => ({
                        ...prev,
                        [selected.id]: event.target.value,
                      }))
                    }
                    rows={12}
                    className="w-full resize-none rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-4 text-sm leading-7 text-slate-200 outline-none focus:border-slate-700"
                  />
                </div>

                <div className="border-t border-slate-800 px-6 py-4">
                  <button
                    type="button"
                    onClick={() => void handleApprove()}
                    disabled={sending}
                    className="w-full rounded-xl bg-emerald-500 py-3.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {sending ? "Sending…" : "Approve & send"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDiscard()}
                    className="mt-2 w-full py-2 text-xs text-slate-500 transition hover:text-slate-300"
                  >
                    Discard
                  </button>
                </div>
              </div>

              {/* Adjust draft */}
              <div className="flex w-80 shrink-0 flex-col bg-slate-950/30 xl:w-96">
                <p className="border-b border-slate-800 px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  Adjust draft
                </p>

                <div className="flex flex-1 flex-col overflow-hidden">
                  <div className="flex-1 space-y-3 overflow-y-auto p-4">
                    {chatMessages.length === 0 && (
                      <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-4 text-sm leading-6 text-slate-400">
                        I&apos;ve drafted a reply based on the email thread. Tell me what to
                        change — tone, length, or details to add — and I&apos;ll update the
                        response on the left. Nothing sends until you approve.
                      </div>
                    )}
                    {chatMessages.map((message) => (
                      <div
                        key={message.id}
                        className={
                          message.role === "user" ? "flex justify-end" : "flex justify-start"
                        }
                      >
                        <div
                          className={`max-w-[92%] rounded-2xl px-3 py-2.5 text-sm leading-6 ${
                            message.role === "user"
                              ? "rounded-br-md bg-slate-800 text-slate-100"
                              : "rounded-bl-md border border-slate-800 bg-slate-900/80 text-slate-300"
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

                  <div className="border-t border-slate-800 p-4">
                    <div className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2">
                      <textarea
                        value={chatInput}
                        onChange={(event) => setChatInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && !event.shiftKey && !adjusting) {
                            event.preventDefault();
                            void handleAdjustDraft();
                          }
                        }}
                        placeholder="e.g. Make it shorter, mention Friday works…"
                        rows={3}
                        disabled={adjusting}
                        className="w-full resize-none bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
