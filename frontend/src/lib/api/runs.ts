import type { AgentStep, SavedChat } from "../../types/research";
import { apiUrl } from "./client";

export type AgentRunSummary = {
  id: string;
  question: string;
  status: string;
  final_answer: string | null;
  created_at: string;
  updated_at: string;
};

type AgentRunStepRow = {
  id: string;
  step_number: number;
  step_type: string;
  content: AgentStep;
  created_at: string;
};

export type AgentRunDetail = AgentRunSummary & {
  steps: AgentRunStepRow[];
};

export async function fetchRuns(limit = 50): Promise<AgentRunSummary[]> {
  const response = await fetch(`${apiUrl}/ai/runs?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Failed to load runs: ${response.status}`);
  }
  return response.json();
}

export async function fetchRun(runId: string): Promise<AgentRunDetail> {
  const response = await fetch(`${apiUrl}/ai/runs/${runId}`);
  if (!response.ok) {
    throw new Error(`Failed to load run: ${response.status}`);
  }
  return response.json();
}

export function runDetailToSavedChat(run: AgentRunDetail): SavedChat {
  const steps = (run.steps ?? [])
    .sort((a, b) => a.step_number - b.step_number)
    .map((row) => row.content);

  const answerStep = steps.find((step) => step.action === "answer");
  const iterations = answerStep?.iteration ?? steps.length;

  return {
    id: run.id,
    question: run.question,
    answer: run.final_answer ?? "",
    steps,
    iterations,
    memory_runs: [],
    created_at: run.created_at,
    saved: true,
  };
}
