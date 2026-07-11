import { supabase } from "../supabase";

export const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function authHeaders(
  extra?: HeadersInit,
): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    ...(extra as Record<string, string> | undefined),
  };
  const token = await getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = await authHeaders(init.headers);
  return fetch(`${apiUrl}${path}`, {
    ...init,
    headers,
  });
}
