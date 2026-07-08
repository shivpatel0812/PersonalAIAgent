/** Microsoft account API helpers. */

import { apiUrl } from "./client";

export type MicrosoftAccountInfo = {
  id: string;
  email: string;
  account_label: string | null;
  granted_services: string[];
  is_primary: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type MicrosoftAccountsListResponse = {
  accounts: MicrosoftAccountInfo[];
};

export type MicrosoftStatus = {
  configured: boolean;
  connected: boolean;
  connect_url: string | null;
  message: string;
};

export async function fetchMicrosoftStatus(): Promise<MicrosoftStatus> {
  const response = await fetch(`${apiUrl}/auth/microsoft/status`);
  if (!response.ok) {
    throw new Error(`Microsoft status check failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchMicrosoftAccounts(): Promise<MicrosoftAccountsListResponse> {
  const response = await fetch(`${apiUrl}/auth/microsoft/accounts`);
  if (!response.ok) {
    throw new Error(`Failed to fetch Microsoft accounts: ${response.status}`);
  }
  return response.json();
}

export async function deleteMicrosoftAccount(accountId: string): Promise<void> {
  const response = await fetch(`${apiUrl}/auth/microsoft/accounts/${accountId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Failed to delete Microsoft account: ${response.status}`);
  }
}

export async function setPrimaryMicrosoftAccount(
  accountId: string
): Promise<MicrosoftAccountInfo> {
  const response = await fetch(`${apiUrl}/auth/microsoft/accounts/${accountId}/set-primary`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Failed to set primary Microsoft account: ${response.status}`);
  }
  return response.json();
}

export async function updateMicrosoftAccountLabel(
  accountId: string,
  label: string | null
): Promise<MicrosoftAccountInfo> {
  const response = await fetch(`${apiUrl}/auth/microsoft/accounts/${accountId}/label`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ label }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update Microsoft account label: ${response.status}`);
  }
  return response.json();
}

export function getMicrosoftConnectUrl(selectAccount = false): string {
  const base = `${import.meta.env.VITE_API_URL}/auth/microsoft/connect`;
  return selectAccount ? `${base}?select_account=true` : base;
}
