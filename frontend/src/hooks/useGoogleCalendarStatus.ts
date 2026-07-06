import { useCallback, useEffect, useState } from "react";
import {
  fetchGoogleCalendarStatus,
  getGoogleConnectUrl,
  type GoogleCalendarStatus,
} from "../lib/api/google";

export function useGoogleCalendarStatus(refreshKey = 0) {
  const [status, setStatus] = useState<GoogleCalendarStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchGoogleCalendarStatus();
      setStatus(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to check Google Calendar");
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload, refreshKey]);

  return {
    status,
    loading,
    error,
    reload,
    connectUrl: status ? getGoogleConnectUrl(status) : null,
  };
}
