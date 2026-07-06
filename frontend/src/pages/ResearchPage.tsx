import { useCallback, useState } from "react";
import { useResearchSettings } from "../context/ResearchSettingsContext";
import { useResearch } from "../hooks/useResearch";
import { useSavedChats } from "../hooks/useSavedChats";
import { extractSourcesFromSteps } from "../lib/utils/research";
import { HistorySidebar } from "../components/history/HistorySidebar";
import { SearchBar } from "../components/research/SearchBar";
import { ReasoningPanel } from "../components/research/ReasoningPanel";
import { AnswerPanel } from "../components/research/AnswerPanel";
import { SourcesPanel } from "../components/research/SourcesPanel";
import { MemoryPanel } from "../components/research/MemoryPanel";
import { ErrorBanner } from "../components/research/ErrorBanner";
import { TweaksPanel } from "../components/tweaks/TweaksPanel";
import type { SavedChat } from "../types/research";

export function ResearchPage() {
  const { placeholder, maxSearches } = useResearchSettings();
  const {
    chats,
    activeChatId,
    loading: historyLoading,
    syncing,
    saveSession,
    markSessionSaved,
    loadChatById,
    removeChat,
    refreshFromServer,
    startNewChat,
  } = useSavedChats();

  const {
    status,
    result,
    error,
    durationMs,
    streamingSteps,
    memoryRuns,
    submitQuestionStreaming,
    loadSession,
    reset,
  } = useResearch({
    onSessionComplete: saveSession,
    onSessionSaved: markSessionSaved,
  });

  const [question, setQuestion] = useState("");

  const handleSubmit = () => {
    void submitQuestionStreaming(question, maxSearches);
  };

  const handleSelectChat = useCallback(
    async (chat: SavedChat) => {
      const loaded = chat.steps.length ? chat : await loadChatById(chat.id);
      if (!loaded) return;
      setQuestion(loaded.question);
      loadSession(loaded);
    },
    [loadChatById, loadSession]
  );

  const handleNewChat = () => {
    startNewChat();
    reset();
    setQuestion("");
  };

  const sources = result ? extractSourcesFromSteps(result.steps) : [];
  const isLoading = status === "loading";

  return (
    <div className="min-h-screen bg-[#070b14]">
      <HistorySidebar
        chats={chats}
        activeChatId={activeChatId}
        loading={historyLoading}
        syncing={syncing}
        onSelect={(chat) => void handleSelectChat(chat)}
        onNewChat={handleNewChat}
        onDelete={removeChat}
        onRefresh={() => void refreshFromServer()}
      />

      <TweaksPanel />

      <main className="ml-72 px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <SearchBar
            value={question}
            placeholder={placeholder}
            loading={isLoading}
            onChange={setQuestion}
            onSubmit={handleSubmit}
          />

          {error && <ErrorBanner message={error} />}

          {memoryRuns.length > 0 && <MemoryPanel runs={memoryRuns} />}

          {(isLoading || result) && (
            <ReasoningPanel
              steps={status === "loading" ? streamingSteps : result?.steps || []}
              durationMs={durationMs}
              loading={isLoading}
            />
          )}

          {result && <AnswerPanel answer={result.answer} />}
          {result && <SourcesPanel sources={sources} />}
        </div>
      </main>
    </div>
  );
}
