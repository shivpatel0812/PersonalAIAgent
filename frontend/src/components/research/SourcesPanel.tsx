import type { SourceItem } from "../../types/research";
import { SectionLabel } from "../ui/SectionLabel";

type SourceCardProps = {
  index: number;
  source: SourceItem;
};

function SourceCard({ index, source }: SourceCardProps) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/50 px-4 py-3 transition hover:border-accent/30 hover:bg-slate-900"
    >
      <span className="font-mono text-xs text-slate-600">{String(index).padStart(2, "0")}</span>
      <span className="h-8 w-8 shrink-0 rounded-lg bg-accent/15" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-slate-200 group-hover:text-white">{source.title}</p>
      </div>
      <span className="shrink-0 font-mono text-xs text-slate-600">{source.domain}</span>
    </a>
  );
}

type SourcesPanelProps = {
  sources: SourceItem[];
};

export function SourcesPanel({ sources }: SourcesPanelProps) {
  if (sources.length === 0) return null;

  return (
    <section className="mt-8">
      <SectionLabel>Sources</SectionLabel>
      <div className="space-y-2">
        {sources.map((source, index) => (
          <SourceCard key={source.id} index={index + 1} source={source} />
        ))}
      </div>
    </section>
  );
}
