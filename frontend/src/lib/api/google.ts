import { apiUrl } from "./client";

export type GoogleCalendarStatus = {
  configured: boolean;
  connected: boolean;
  calendar_access: boolean;
  calendar_summary: string | null;
  upcoming_events_sample: number | null;
  connect_url: string | null;
  redirect_uri: string | null;
  oauth_client_id: string | null;
  message: string;
};

export async function fetchGoogleCalendarStatus(): Promise<GoogleCalendarStatus> {
  const response = await fetch(`${apiUrl}/auth/google/status`);
  if (!response.ok) {
    throw new Error(`Google status check failed: ${response.status}`);
  }
  return response.json();
}

export async function disconnectGoogleCalendar(): Promise<void> {
  const response = await fetch(`${apiUrl}/auth/google/disconnect`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to disconnect Google Calendar: ${response.status}`);
  }
}

export function getGoogleConnectUrl(status: GoogleCalendarStatus): string | null {
  if (!status.connect_url) return null;
  return `${apiUrl}${status.connect_url}`;
}
