import { useEffect, useState } from "react";
import { useResearchSettings } from "../context/ResearchSettingsContext";
import { useChatThreads } from "../hooks/useChatThreads";
import { useConversation } from "../hooks/useConversation";
import { PageNav } from "../components/layout/PageNav";
import { ChatSidebar } from "../components/conversation/ChatSidebar";
import { ConversationThread } from "../components/conversation/ConversationThread";
import { ConversationInput } from "../components/conversation/ConversationInput";
import { MemoryPanel } from "../components/research/MemoryPanel";
import { ErrorBanner } from "../components/research/ErrorBanner";
import { TweaksPanel } from "../components/tweaks/TweaksPanel";
import { GoogleCalendarPanel } from "../components/integrations/GoogleCalendarPanel";
import { RESEARCH_PAGES, getPageConfig, type PageType } from "../types/conversation";

export function ConversationPage() {
  const { maxSearches } = useResearchSettings();
  const [activePage, setActivePage] = useState<PageType>("general");
  const [googleRefreshKey, setGoogleRefreshKey] = useState(0);
  const [googleOauthReturn, setGoogleOauthReturn] = useState<"connected" | "error" | null>(null);
  const [googleOauthError, setGoogleOauthError] = useState<string | null>(null);
  const pageConfig = getPageConfig(activePage);

  const {
    threads,
    activeThreadId,
    loadingThreads,
    error: threadsError,
    selectThread,
    createNewChat,
    removeThread,
  } = useChatThreads(activePage);

  const {
    messages,
    status,
    error,
    streamingSteps,
    memoryRuns,
    loadingConversation,
    pendingQuestion,
    submitMessage,
    clearMessages,
  } = useConversation(activePage, activeThreadId);

  const [input, setInput] = useState("");
  const isLoading = status === "loading";
  const displayError = error ?? threadsError;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const googleStatus = params.get("google_calendar");
    if (!googleStatus) return;

    if (googleStatus === "connected") {
      setGoogleOauthReturn("connected");
      setGoogleRefreshKey((value) => value + 1);
    } else if (googleStatus === "error") {
      const message =
        params.get("message")?.replace(/\+/g, " ") ||
        "Google sign-in failed. Try again.";
      setGoogleOauthReturn("error");
      setGoogleOauthError(decodeURIComponent(message));
    }

    setActivePage("personal");

    params.delete("google_calendar");
    params.delete("message");
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
    window.history.replaceState({}, "", next);
  }, []);

  const handleNewChat = () => {
    void (async () => {
      clearMessages();
      await createNewChat();
    })();
  };

  const handleDeleteChat = (threadId: string) => {
    void removeThread(threadId);
  };

  const handleSubmit = () => {
    const question = input;
    setInput("");
    void submitMessage(question, maxSearches);
  };

  return (
    <div className="flex min-h-screen bg-[#070b14]">
      <PageNav
        pages={RESEARCH_PAGES}
        activePage={activePage}
        onSelect={setActivePage}
      />

      <ChatSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        loading={loadingThreads}
        onSelect={selectThread}
        onNewChat={handleNewChat}
        onDelete={handleDeleteChat}
      />

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="border-b border-slate-800 px-6 py-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
            Probe research agent
          </p>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">{pageConfig.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{pageConfig.description}</p>
        </header>

        <div className="flex flex-1 flex-col px-6">
          {displayError && (
            <div className="pt-4">
              <ErrorBanner message={displayError} />
            </div>
          )}

          {activePage === "personal" && (
            <div className="pt-4">
              <GoogleCalendarPanel
                refreshKey={googleRefreshKey}
                oauthReturn={googleOauthReturn}
                oauthErrorMessage={googleOauthError}
              />
            </div>
          )}

          {memoryRuns.length > 0 && isLoading && (
            <div className="pt-4">
              <MemoryPanel runs={memoryRuns} />
            </div>
          )}

          <ConversationThread
            messages={messages}
            loadingConversation={loadingConversation || loadingThreads}
            isResearching={isLoading}
            pendingQuestion={pendingQuestion}
            streamingSteps={streamingSteps}
            memoryRunsCount={memoryRuns.length}
          />

          <ConversationInput
            value={input}
            placeholder={
              messages.length > 0
                ? "Ask a follow-up…"
                : pageConfig.placeholder
            }
            loading={isLoading}
            disabled={!activeThreadId}
            onChange={setInput}
            onSubmit={handleSubmit}
          />
        </div>
      </div>

      <TweaksPanel />
    </div>
  );
}
