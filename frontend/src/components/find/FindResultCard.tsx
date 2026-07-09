import type { FindResult } from "../../types/find";

type FindResultCardProps = {
  result: FindResult;
  onThumb: (index: number, value: "up" | "down") => void;
  disabled?: boolean;
};

export function FindResultCard({ result, onThumb, disabled = false }: FindResultCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-slate-500">#{result.index}</p>
          <h3 className="mt-1 text-sm font-medium text-slate-100">{result.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-400">{result.snippet}</p>
          <a
            href={result.url}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-xs text-accent hover:underline"
          >
            Open link
          </a>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            disabled={disabled}
            onClick={() => onThumb(result.index, "up")}
            className="rounded-lg border border-slate-700 px-2 py-1 text-sm text-slate-400 transition hover:border-emerald-500/40 hover:text-emerald-300 disabled:opacity-40"
            title="Like this result"
          >
            👍
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onThumb(result.index, "down")}
            className="rounded-lg border border-slate-700 px-2 py-1 text-sm text-slate-400 transition hover:border-rose-500/40 hover:text-rose-300 disabled:opacity-40"
            title="Dislike this result"
          >
            👎
          </button>
        </div>
      </div>
    </div>
  );
}
