import { useGoogleCalendarStatus } from "../../hooks/useGoogleCalendarStatus";
import { disconnectGoogleCalendar, fetchGoogleCalendarStatus, getGoogleConnectUrl } from "../../lib/api/google";

type GoogleCalendarPanelProps = {
  refreshKey?: number;
};

export function GoogleCalendarPanel({ refreshKey = 0 }: GoogleCalendarPanelProps) {
  const { status, loading, error, reload, connectUrl } = useGoogleCalendarStatus(refreshKey);

  async function handleReconnect() {
    await disconnectGoogleCalendar();
    const fresh = await fetchGoogleCalendarStatus();
    await reload();
    const url = getGoogleConnectUrl(fresh);
    if (url) {
      window.location.href = url;
    }
  }

  if (loading) {
    return (
      <section className="mb-4 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
        <p className="text-sm text-slate-500">Checking Google Calendar…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
        <p className="text-sm text-red-300">{error}</p>
      </section>
    );
  }

  if (!status) return null;

  const isWorking = status.configured && status.connected && status.calendar_access;

  return (
    <section
      className={`mb-4 rounded-xl border px-4 py-3 ${
        isWorking
          ? "border-emerald-500/30 bg-emerald-500/10"
          : "border-slate-800 bg-slate-900/40"
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-slate-200">Google Calendar</p>
        <button
          type="button"
          onClick={() => void reload()}
          className="text-xs text-slate-500 transition hover:text-slate-300"
        >
          Refresh
        </button>
      </div>

      <div className="space-y-1 text-xs text-slate-400">
        <p>Configured: {status.configured ? "Yes" : "No"}</p>
        <p>Connected: {status.connected ? "Yes" : "No"}</p>
        <p>Calendar access: {status.calendar_access ? "Yes" : "No"}</p>
        {status.calendar_summary && <p>Calendar: {status.calendar_summary}</p>}
      </div>

      <p className="mt-3 text-sm text-slate-300">{status.message}</p>

      {status.redirect_uri && !isWorking && (
        <div className="mt-2 space-y-1 text-xs text-slate-500">
          <p>
            Redirect URI (must be on the OAuth client below):{" "}
            <code className="text-slate-300">{status.redirect_uri}</code>
          </p>
          {status.oauth_client_id && (
            <p>
              OAuth client ID (open this exact client in Google Cloud):{" "}
              <code className="break-all text-slate-300">{status.oauth_client_id}</code>
            </p>
          )}
        </div>
      )}

      {connectUrl && !isWorking && (
        status.connected && !status.calendar_access ? (
          <button
            type="button"
            onClick={() => void handleReconnect()}
            className="mt-3 inline-block rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 transition hover:border-accent"
          >
            Reconnect Google Calendar
          </button>
        ) : (
          <a
            href={connectUrl}
            className="mt-3 inline-block rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 transition hover:border-accent"
          >
            Connect Google Calendar
          </a>
        )
      )}
    </section>
  );
}
