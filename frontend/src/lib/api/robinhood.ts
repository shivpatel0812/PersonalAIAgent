import { apiFetch, apiUrl } from "./client";
import type { RobinhoodStatus, RobinhoodToolInfo } from "../../types/robinhood";

export async function fetchRobinhoodStatus(): Promise<RobinhoodStatus> {
  const response = await apiFetch("/auth/robinhood/status");
  if (!response.ok) {
    throw new Error(`Robinhood status check failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchRobinhoodTools(): Promise<RobinhoodToolInfo[]> {
  const response = await apiFetch("/auth/robinhood/tools");
  if (!response.ok) {
    throw new Error(`Failed to fetch Robinhood tools: ${response.status}`);
  }
  const data = await response.json();
  return data.tools ?? [];
}

export function getRobinhoodConnectUrl(): string {
  return `${apiUrl}/auth/robinhood/connect`;
}

export async function disconnectRobinhood(): Promise<void> {
  const response = await apiFetch("/auth/robinhood/disconnect", {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to disconnect Robinhood: ${response.status}`);
  }
}
