import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "../research/ErrorBanner";
import {
  createFindSession,
  resetFindSession,
  sendFindMessage,
} from "../../lib/api/find";
import type { FindMessage, FindTurnResponse } from "../../types/find";
import { FindMessageList } from "./FindMessageList";

export function FindPanel() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<FindMessage[]>([]);
  const [phase, setPhase] = useState<"gathering" | "results">("gathering");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ratings, setRatings] = useState<Map<number, "up" | "down">>(new Map());

  const hasRatings = ratings.size > 0;

  const applyResponse = useCallback((response: FindTurnResponse) => {
    setSessionId(response.session_id);
    setMessages(response.messages);
    setPhase(response.phase);
    // Clear ratings when new results arrive
    setRatings(new Map());
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const id = await createFindSession();
        if (!cancelled) {
          setSessionId(id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to start find session");
        }
      } finally {
        if (!cancelled) {
          setBootstrapping(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSend = async (
    message: string,
    feedback?: { type: "thumb"; index: number; value: "up" | "down" } | { type: "refine"; ratings: Array<{ index: number; value: "up" | "down" }> }
  ) => {
    if (!sessionId || loading) return;
    const trimmed = message.trim();
    if (!trimmed && !feedback) return;

    setLoading(true);
    setError(null);
    try {
      const response = await sendFindMessage(sessionId, trimmed, feedback);
      applyResponse(response);
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    void handleSend(input);
  };

  const handleThumb = (index: number, value: "up" | "down") => {
    setRatings((prev) => {
      const next = new Map(prev);
      if (next.get(index) === value) {
        next.delete(index); // Toggle off if same button clicked again
      } else {
        next.set(index, value);
      }
      return next;
    });
  };

  const handleRefineSearch = () => {
    const ratingsArray = Array.from(ratings.entries()).map(([index, value]) => ({
      index,
      value,
    }));
    void handleSend("", { type: "refine", ratings: ratingsArray });
  };

  const handleNewSearch = async () => {
    if (!sessionId || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await resetFindSession(sessionId);
      applyResponse(response);
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {error && (
        <div className="px-6 pt-4">
          <ErrorBanner message={error} />
        </div>
      )}

      <FindMessageList
        messages={messages}
        loading={loading || bootstrapping}
        onThumb={handleThumb}
        thumbDisabled={loading || phase !== "results"}
        ratings={ratings}
        showRefineButton={hasRatings && !loading}
        onRefineSearch={handleRefineSearch}
      />

      <div className="border-t border-slate-800 px-6 py-4">
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder={
              phase === "results"
                ? 'Refine results — "cheaper", "more like #3", "stainless steel"…'
                : "Find me a water bottle, flights to NYC, work clothes under $200…"
            }
            disabled={loading || bootstrapping || !sessionId}
            rows={2}
            className="min-h-[52px] flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-accent/50 focus:outline-none disabled:opacity-50"
          />
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading || bootstrapping || !sessionId || !input.trim()}
              className="rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-accent/90 disabled:opacity-40"
            >
              {loading ? "…" : "Send"}
            </button>
            <button
              type="button"
              onClick={() => void handleNewSearch()}
              disabled={loading || bootstrapping || !sessionId}
              className="rounded-xl border border-slate-700 px-4 py-2 text-xs text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
            >
              New search
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
