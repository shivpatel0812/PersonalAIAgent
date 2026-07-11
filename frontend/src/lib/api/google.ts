import { apiFetch, apiUrl } from "./client";

export type ServiceInfo = {
  name: string;
  label: string;
  description: string;
  scopes: string[];
};

export type AvailableServicesResponse = {
  services: ServiceInfo[];
};

export type GoogleCalendarStatus = {
  configured: boolean;
  connected: boolean;
  calendar_access: boolean;
  gmail_access?: boolean;
  drive_access?: boolean;
  granted_services?: string[];
  calendar_summary: string | null;
  upcoming_events_sample: number | null;
  connect_url: string | null;
  redirect_uri: string | null;
  oauth_client_id: string | null;
  message: string;
};

export type AccountInfo = {
  id: string;
  email: string;
  account_label: string | null;
  granted_services: string[];
  is_primary: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type AccountsListResponse = {
  accounts: AccountInfo[];
};

export async function fetchAvailableServices(): Promise<AvailableServicesResponse> {
  const response = await apiFetch("/auth/google/services");
  if (!response.ok) {
    throw new Error(`Failed to fetch available services: ${response.status}`);
  }
  return response.json();
}

export async function fetchGoogleCalendarStatus(): Promise<GoogleCalendarStatus> {
  const response = await apiFetch("/auth/google/status");
  if (!response.ok) {
    throw new Error(`Google status check failed: ${response.status}`);
  }
  return response.json();
}

export async function disconnectGoogleCalendar(): Promise<void> {
  const response = await apiFetch("/auth/google/disconnect", { method: "POST" });
  if (!response.ok) {
    throw new Error(`Failed to disconnect Google Calendar: ${response.status}`);
  }
}

export function getGoogleConnectUrl(status: GoogleCalendarStatus, selectedServices?: string[]): string | null {
  if (!status.connect_url) return null;

  let url = `${apiUrl}${status.connect_url}`;

  if (selectedServices && selectedServices.length > 0) {
    const params = selectedServices.map(s => `services=${encodeURIComponent(s)}`).join('&');
    url += `?${params}`;
  }

  return url;
}

export async function fetchAccounts(): Promise<AccountsListResponse> {
  const response = await apiFetch("/auth/google/accounts");
  if (!response.ok) {
    throw new Error(`Failed to fetch accounts: ${response.status}`);
  }
  return response.json();
}

export async function deleteAccount(accountId: string): Promise<void> {
  const response = await apiFetch(`/auth/google/accounts/${accountId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete account: ${response.status}`);
  }
}

export async function setPrimaryAccount(accountId: string): Promise<AccountInfo> {
  const response = await apiFetch(`/auth/google/accounts/${accountId}/set-primary`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to set primary account: ${response.status}`);
  }
  return response.json();
}

export async function updateAccountLabel(accountId: string, label: string | null): Promise<AccountInfo> {
  const response = await apiFetch(`/auth/google/accounts/${accountId}/label`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ label }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update account label: ${response.status}`);
  }
  return response.json();
}
