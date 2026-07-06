import type { PastRunMemory } from "../../types/research";
import { formatMemoryDate } from "../../lib/utils/research";
import { Badge } from "../ui/Badge";

type MemoryPanelProps = {
  runs: PastRunMemory[];
};

export function MemoryPanel({ runs }: MemoryPanelProps) {
  if (runs.length === 0) return null;

  return (
    <section className="mb-8 rounded-2xl border border-violet-500/20 bg-violet-500/5 p-5">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="text-sm font-medium text-slate-200">Recalled from memory</h2>
        <Badge>{runs.length}</Badge>
      </div>
      <p className="mb-4 text-sm text-slate-400">
        Related past research was loaded before this session started.
      </p>
      <div className="space-y-3">
        {runs.map((run) => (
          <article
            key={run.id}
            className="rounded-xl border border-slate-800 bg-slate-950/40 px-4 py-3"
          >
            <div className="mb-1 flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-slate-200">{run.question}</p>
              <div className="flex shrink-0 items-center gap-2">
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                  run.search_method === 'vector'
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                    : 'border-amber-500/30 bg-amber-500/10 text-amber-400'
                }`}>
                  {run.search_method}
                </span>
                <span className="text-xs text-slate-500">
                  {formatMemoryDate(run.created_at)}
                </span>
              </div>
            </div>
            <p className="line-clamp-3 text-xs leading-6 text-slate-400">
              {run.answer_preview}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
