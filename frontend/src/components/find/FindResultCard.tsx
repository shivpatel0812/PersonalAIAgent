import type { FindResult } from "../../types/find";

type FindResultCardProps = {
  result: FindResult;
  onThumb: (index: number, value: "up" | "down") => void;
  disabled?: boolean;
};

function truncate(text: string, maxLength: number): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLength) return cleaned;
  return `${cleaned.slice(0, maxLength - 1).trim()}…`;
}

export function FindResultCard({ result, onThumb, disabled = false }: FindResultCardProps) {
  return (
    <article className="group flex flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-950/80 transition hover:border-slate-700">
      <a
        href={result.url}
        target="_blank"
        rel="noreferrer"
        className="relative block aspect-[4/3] overflow-hidden bg-slate-900"
      >
        {result.image_url ? (
          <img
            src={result.image_url}
            alt={result.title}
            className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(event) => {
              event.currentTarget.style.display = "none";
            }}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center px-4 text-center text-xs text-slate-500">
            No preview image
          </div>
        )}
        <span className="absolute left-2 top-2 rounded-md bg-black/60 px-2 py-0.5 text-[10px] font-medium text-slate-200">
          #{result.index}
        </span>
      </a>

      <div className="flex flex-1 flex-col p-3">
        <a
          href={result.url}
          target="_blank"
          rel="noreferrer"
          className="line-clamp-2 text-sm font-medium leading-5 text-slate-100 hover:text-accent"
        >
          {result.title}
        </a>
        <p className="mt-2 line-clamp-3 flex-1 text-xs leading-5 text-slate-400">
          {truncate(result.snippet, 180)}
        </p>
        <div className="mt-3 flex items-center justify-between gap-2">
          <a
            href={result.url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-accent hover:underline"
          >
            Open link
          </a>
          <div className="flex gap-1">
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
    </article>
  );
}
