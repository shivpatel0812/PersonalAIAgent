import type { SearchResult } from "../../types/research";
import { getDomainFromUrl } from "../../lib/utils/research";

type SourceLinkProps = {
  result: SearchResult;
};

export function SourceLink({ result }: SourceLinkProps) {
  return (
    <a
      href={result.url}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center justify-between gap-3 rounded-lg border border-slate-800/80 bg-slate-950/50 px-3 py-2 transition hover:border-accent/30 hover:bg-slate-900"
    >
      <span className="truncate text-sm text-slate-300 group-hover:text-slate-100">
        {result.title}
      </span>
      <span className="shrink-0 font-mono text-xs text-slate-600">
        {getDomainFromUrl(result.url)}
      </span>
    </a>
  );
}
