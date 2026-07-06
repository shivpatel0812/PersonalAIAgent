const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: string;
  supabase_configured: boolean;
  supabase_connected: boolean;
  openai_configured?: boolean;
  tavily_configured?: boolean;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiUrl}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }

  return response.json();
}
