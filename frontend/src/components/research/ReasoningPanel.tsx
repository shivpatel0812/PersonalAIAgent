import type { AgentStep } from "../../types/research";
import { getReasoningSteps, formatDuration } from "../../lib/utils/research";
import { SectionLabel } from "../ui/SectionLabel";
import { ReasoningIteration } from "./ReasoningIteration";

type ReasoningPanelProps = {
  steps: AgentStep[];
  durationMs: number | null;
  loading?: boolean;
};

export function ReasoningPanel({ steps, durationMs, loading = false }: ReasoningPanelProps) {
  const reasoningSteps = getReasoningSteps(steps);

  if (loading) {
    return (
      <section className="mt-8">
        <SectionLabel
          right={
            <span className="flex items-center gap-2 font-mono text-xs text-slate-500">
              <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
              running
            </span>
          }
        >
          Reasoning
        </SectionLabel>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-6">
          <p className="text-sm text-slate-500">Searching, reading pages, and synthesizing...</p>
        </div>
      </section>
    );
  }

  if (reasoningSteps.length === 0) return null;

  return (
    <section className="mt-8">
      <SectionLabel
        right={
          durationMs !== null ? (
            <span className="flex items-center gap-2 font-mono text-xs text-slate-500">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              {formatDuration(durationMs)}
            </span>
          ) : null
        }
      >
        Reasoning
      </SectionLabel>
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-4">
        {reasoningSteps.map((step, index) => (
          <ReasoningIteration
            key={`${step.iteration}-${step.action}-${step.query ?? step.url}`}
            step={step}
            isLast={index === reasoningSteps.length - 1}
          />
        ))}
      </div>
    </section>
  );
}
