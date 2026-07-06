import { useEffect, useState } from "react";
import { useResearchSettings } from "../context/ResearchSettingsContext";
import { useConversation } from "../hooks/useConversation";
import { PageNav } from "../components/layout/PageNav";
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
  const pageConfig = getPageConfig(activePage);

  const {
    messages,
    status,
    error,
    streamingSteps,
    memoryRuns,
    loadingConversation,
    pendingQuestion,
    submitMessage,
  } = useConversation(activePage);

  const [input, setInput] = useState("");
  const isLoading = status === "loading";

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const googleStatus = params.get("google_calendar");
    if (googleStatus) {
      setGoogleRefreshKey((value) => value + 1);
      if (activePage !== "personal") {
        setActivePage("personal");
      }
      params.delete("google_calendar");
      params.delete("message");
      const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}`;
      window.history.replaceState({}, "", next);
    }
  }, [activePage]);

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

      <div className="ml-72 flex min-h-screen flex-1 flex-col">
        <header className="border-b border-slate-800 px-6 py-5">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
            Probe research agent
          </p>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">{pageConfig.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{pageConfig.description}</p>
        </header>

        <div className="flex flex-1 flex-col px-6">
          {error && <div className="pt-4"><ErrorBanner message={error} /></div>}

          {activePage === "personal" && (
            <div className="pt-4">
              <GoogleCalendarPanel refreshKey={googleRefreshKey} />
            </div>
          )}

          {memoryRuns.length > 0 && isLoading && (
            <div className="pt-4">
              <MemoryPanel runs={memoryRuns} />
            </div>
          )}

          <ConversationThread
            messages={messages}
            loadingConversation={loadingConversation}
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
            onChange={setInput}
            onSubmit={handleSubmit}
          />
        </div>
      </div>

      <TweaksPanel />
    </div>
  );
}
