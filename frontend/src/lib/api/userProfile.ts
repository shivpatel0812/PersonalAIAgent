import { apiUrl } from "./client";
import type { UserEmailProfile } from "../../types/userProfile";

export async function fetchUserEmailProfile(): Promise<UserEmailProfile> {
  const response = await fetch(`${apiUrl}/user/email-profile`);
  if (!response.ok) {
    throw new Error(`Failed to load reply preferences: ${response.status}`);
  }
  return response.json();
}

export async function saveUserEmailProfile(
  profile: Partial<UserEmailProfile>
): Promise<UserEmailProfile> {
  const response = await fetch(`${apiUrl}/user/email-profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!response.ok) {
    throw new Error(`Failed to save reply preferences: ${response.status}`);
  }
  return response.json();
}
