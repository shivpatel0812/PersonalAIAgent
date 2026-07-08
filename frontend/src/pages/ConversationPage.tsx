import { useEffect, useState } from "react";
import { useResearchSettings } from "../context/ResearchSettingsContext";
import { useChatThreads } from "../hooks/useChatThreads";
import { useConversation } from "../hooks/useConversation";
import { PageNav, type PersonalSubView } from "../components/layout/PageNav";
import { ChatSidebar } from "../components/conversation/ChatSidebar";
import { ConversationThread } from "../components/conversation/ConversationThread";
import { ConversationInput } from "../components/conversation/ConversationInput";
import { MemoryPanel } from "../components/research/MemoryPanel";
import { ErrorBanner } from "../components/research/ErrorBanner";
import { TweaksPanel } from "../components/tweaks/TweaksPanel";
import { GoogleCalendarPanel } from "../components/integrations/GoogleCalendarPanel";
import { RobinhoodPanel } from "../components/integrations/RobinhoodPanel";
import { EmailAgentPanel } from "../components/email-agent/EmailAgentPanel";
import { fetchEmailAgentItems } from "../lib/api/emailAgent";
import { RESEARCH_PAGES, getPageConfig, type PageType } from "../types/conversation";

export function ConversationPage() {
  const { maxSearches } = useResearchSettings();
  const [activePage, setActivePage] = useState<PageType>("general");
  const [googleRefreshKey, setGoogleRefreshKey] = useState(0);
  const [googleOauthReturn, setGoogleOauthReturn] = useState<"connected" | "error" | null>(null);
  const [googleOauthError, setGoogleOauthError] = useState<string | null>(null);
  const [microsoftRefreshKey, setMicrosoftRefreshKey] = useState(0);
  const [microsoftOauthReturn, setMicrosoftOauthReturn] = useState<"connected" | "error" | null>(null);
  const [microsoftOauthError, setMicrosoftOauthError] = useState<string | null>(null);
  const [robinhoodRefreshKey, setRobinhoodRefreshKey] = useState(0);
  const [robinhoodOauthReturn, setRobinhoodOauthReturn] = useState<"connected" | "error" | null>(null);
  const [robinhoodOauthError, setRobinhoodOauthError] = useState<string | null>(null);
  const [personalView, setPersonalView] = useState<PersonalSubView>("chat");
  const [emailAgentCount, setEmailAgentCount] = useState(0);
  const pageConfig = getPageConfig(activePage);
  const isEmailAgentView = activePage === "personal" && personalView === "email-agent";

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const microsoftStatus = params.get("microsoft");
    if (!microsoftStatus) return;

    if (microsoftStatus === "connected") {
      setMicrosoftOauthReturn("connected");
      setMicrosoftRefreshKey((value) => value + 1);
    } else if (microsoftStatus === "error") {
      const message =
        params.get("message")?.replace(/\+/g, " ") ||
        "Microsoft sign-in failed. Try again.";
      setMicrosoftOauthReturn("error");
      setMicrosoftOauthError(decodeURIComponent(message));
    }

    setActivePage("personal");
    setPersonalView("email-agent");

    params.delete("microsoft");
    params.delete("message");
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
    window.history.replaceState({}, "", next);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const robinhoodStatus = params.get("robinhood");
    if (!robinhoodStatus) return;

    if (robinhoodStatus === "connected") {
      setRobinhoodOauthReturn("connected");
      setRobinhoodRefreshKey((value) => value + 1);
    } else if (robinhoodStatus === "error") {
      const message =
        params.get("message")?.replace(/\+/g, " ") ||
        "Robinhood sign-in failed. Try again.";
      setRobinhoodOauthReturn("error");
      setRobinhoodOauthError(decodeURIComponent(message));
    }

    const page = params.get("page");
    if (page === "stocks") {
      setActivePage("stocks");
    }

    params.delete("robinhood");
    params.delete("page");
    params.delete("message");
    const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
    window.history.replaceState({}, "", next);
  }, []);

  useEffect(() => {
    if (activePage !== "personal") return;

    void fetchEmailAgentItems()
      .then((items) => setEmailAgentCount(items.length))
      .catch(() => setEmailAgentCount(0));
  }, [activePage, personalView]);

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

  const handleSelectPage = (pageType: PageType) => {
    setActivePage(pageType);
    if (pageType === "personal") {
      setPersonalView("chat");
    }
  };

  return (
    <div className="flex min-h-screen bg-[#070b14]">
      <PageNav
        pages={RESEARCH_PAGES}
        activePage={activePage}
        onSelect={handleSelectPage}
        personalSubView={personalView}
        onPersonalSubViewChange={setPersonalView}
        emailAgentCount={emailAgentCount}
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
          {isEmailAgentView ? (
            <>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Personal Assistant / Email Agent
              </p>
              <div className="mt-2 flex items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-semibold text-slate-100">Email Agent</h1>
                  <p className="mt-1 text-sm text-slate-500">
                    Responses need your approval before anything is sent
                  </p>
                </div>
                {emailAgentCount > 0 && (
                  <span className="shrink-0 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-300">
                    {emailAgentCount} need a response
                  </span>
                )}
              </div>
            </>
          ) : (
            <>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
                Probe research agent
              </p>
              <h1 className="mt-1 text-xl font-semibold text-slate-100">{pageConfig.title}</h1>
              <p className="mt-1 text-sm text-slate-500">{pageConfig.description}</p>
            </>
          )}
        </header>

        {isEmailAgentView ? (
          <EmailAgentPanel
            googleRefreshKey={googleRefreshKey}
            googleOauthReturn={googleOauthReturn}
            googleOauthError={googleOauthError}
            microsoftRefreshKey={microsoftRefreshKey}
            microsoftOauthReturn={microsoftOauthReturn}
            microsoftOauthError={microsoftOauthError}
            onQueueCountChange={setEmailAgentCount}
          />
        ) : (
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

            {activePage === "stocks" && (
              <div className="pt-4">
                <RobinhoodPanel
                  refreshKey={robinhoodRefreshKey}
                  oauthReturn={robinhoodOauthReturn}
                  oauthErrorMessage={robinhoodOauthError}
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
                messages.length > 0 ? "Ask a follow-up…" : pageConfig.placeholder
              }
              loading={isLoading}
              disabled={!activeThreadId}
              onChange={setInput}
              onSubmit={handleSubmit}
            />
          </div>
        )}
      </div>

      <TweaksPanel />
    </div>
  );
}
