import type { AgentStep, SourceItem } from "../../types/research";

export function getDomainFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function extractSourcesFromSteps(steps: AgentStep[]): SourceItem[] {
  const seen = new Set<string>();
  const sources: SourceItem[] = [];

  for (const step of steps) {
    if (step.search_results) {
      for (const result of step.search_results) {
        if (!result.url || seen.has(result.url)) continue;
        seen.add(result.url);
        sources.push({
          id: result.url,
          title: result.title || result.url,
          url: result.url,
          domain: getDomainFromUrl(result.url),
        });
      }
    }

    if (step.action === "scrape" && step.url && !seen.has(step.url)) {
      seen.add(step.url);
      sources.push({
        id: step.url,
        title: step.scraped_title || step.url,
        url: step.url,
        domain: getDomainFromUrl(step.url),
      });
    }
  }

  return sources;
}

export function getSearchSteps(steps: AgentStep[]): AgentStep[] {
  return steps.filter((step) => step.action === "search" && step.query);
}

export function getReasoningSteps(steps: AgentStep[]): AgentStep[] {
  return steps.filter((step) => step.action === "search" || step.action === "scrape");
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatMemoryDate(createdAt: string): string {
  if (!createdAt) return "Unknown date";
  const parsed = new Date(createdAt);
  if (Number.isNaN(parsed.getTime())) return createdAt.slice(0, 10);
  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
