import type { AgentStep } from "../../types/research";
import { getDomainFromUrl } from "../../lib/utils/research";
import { Badge } from "../ui/Badge";
import { SourceLink } from "./SourceLink";

type ReasoningIterationProps = {
  step: AgentStep;
  isLast: boolean;
};

function SearchStepContent({ step }: { step: AgentStep }) {
  return (
    <>
      <p className="mb-3 text-sm italic text-slate-400">&ldquo;{step.query}&rdquo;</p>
      <div className="space-y-2">
        {step.search_results?.map((result) => (
          <SourceLink key={result.url} result={result} />
        ))}
      </div>
    </>
  );
}

function ScrapeStepContent({ step }: { step: AgentStep }) {
  const charCount = step.scraped_content?.length ?? 0;

  return (
    <>
      <a
        href={step.url ?? "#"}
        target="_blank"
        rel="noreferrer"
        className="mb-2 block truncate text-sm text-accent hover:underline"
      >
        {step.scraped_title || step.url}
      </a>
      <p className="mb-2 font-mono text-xs text-slate-500">
        {getDomainFromUrl(step.url ?? "")} · {charCount.toLocaleString()} chars
        {step.content_truncated ? " · truncated" : ""}
      </p>
      {step.scraped_content && (
        <p className="line-clamp-4 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-xs leading-6 text-slate-400">
          {step.scraped_content.slice(0, 400)}
          {step.scraped_content.length > 400 ? "…" : ""}
        </p>
      )}
    </>
  );
}

export function ReasoningIteration({ step, isLast }: ReasoningIterationProps) {
  const isScrape = step.action === "scrape";

  return (
    <div className="relative pl-6">
      <span
        className={`absolute left-[7px] top-3 w-px bg-slate-800 ${isLast ? "h-3" : "bottom-0"}`}
      />
      <span className="absolute left-0 top-2 h-3.5 w-3.5 rounded-full border-2 border-accent bg-slate-950" />

      <div className="pb-6">
        <div className="mb-2 flex items-center gap-2">
          <span className="text-xs text-slate-500">Iteration {step.iteration}</span>
          <Badge>{isScrape ? "Read" : "Search"}</Badge>
        </div>

        {isScrape ? <ScrapeStepContent step={step} /> : <SearchStepContent step={step} />}
      </div>
    </div>
  );
}
