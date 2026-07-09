import type { FindMessage } from "../../types/find";
import { FindResultCard } from "./FindResultCard";

type FindMessageListProps = {
  messages: FindMessage[];
  loading?: boolean;
  onThumb: (index: number, value: "up" | "down") => void;
  thumbDisabled?: boolean;
};

export function FindMessageList({
  messages,
  loading = false,
  onThumb,
  thumbDisabled = false,
}: FindMessageListProps) {
  if (messages.length === 0 && !loading) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 py-12 text-center">
        <div>
          <p className="text-sm text-slate-300">What are you looking for?</p>
          <p className="mt-2 text-xs text-slate-500">
            Try a water bottle, flights to NYC, work clothes, a restaurant — anything.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const results = message.payload?.results ?? [];

        return (
          <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-2xl rounded-2xl px-4 py-3 ${
                isUser
                  ? "bg-accent/15 text-slate-100"
                  : "border border-slate-800 bg-slate-900/60 text-slate-200"
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
              {!isUser && results.length > 0 && (
                <div className="mt-4 space-y-3">
                  {results.map((result) => (
                    <FindResultCard
                      key={`${message.id}-${result.index}`}
                      result={result}
                      onThumb={onThumb}
                      disabled={thumbDisabled}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {loading && (
        <div className="flex justify-start">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm text-slate-400">
            Thinking…
          </div>
        </div>
      )}
    </div>
  );
}
