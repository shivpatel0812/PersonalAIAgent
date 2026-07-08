import { useEffect, useState } from "react";
import {
  disconnectRobinhood,
  fetchRobinhoodStatus,
  getRobinhoodConnectUrl,
} from "../../lib/api/robinhood";
import type { RobinhoodStatus } from "../../types/robinhood";

type RobinhoodPanelProps = {
  refreshKey?: number;
  oauthReturn?: "connected" | "error" | null;
  oauthErrorMessage?: string | null;
};

export function RobinhoodPanel({
  refreshKey = 0,
  oauthReturn = null,
  oauthErrorMessage = null,
}: RobinhoodPanelProps) {
  const [status, setStatus] = useState<RobinhoodStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  async function loadStatus() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRobinhoodStatus();
      setStatus(data);
      if (!data.connected) {
        setExpanded(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Robinhood status");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (oauthReturn === "error") {
      setError(oauthErrorMessage || "Robinhood sign-in failed. Try again.");
      setLoading(false);
      setExpanded(true);
      return;
    }
    void loadStatus();
  }, [refreshKey, oauthReturn, oauthErrorMessage]);

  function handleConnect() {
    sessionStorage.setItem("robinhood_oauth_pending", "1");
    window.location.href = getRobinhoodConnectUrl();
  }

  async function handleDisconnect() {
    if (!confirm("Disconnect Robinhood MCP from this app?")) return;
    try {
      await disconnectRobinhood();
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disconnect");
    }
  }

  const countLabel = loading
    ? "Loading…"
    : status?.connected
      ? "Connected"
      : "Not connected";

  return (
    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-emerald-500/5"
      >
        <span className="text-sm text-slate-200">
          Robinhood MCP <span className="text-slate-500">•</span> {countLabel}
        </span>
        <span className={`text-slate-500 transition ${expanded ? "rotate-180" : ""}`}>▾</span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-emerald-500/10 px-4 py-4">
          {error && <p className="text-sm text-red-300">{error}</p>}

          {status && (
            <>
              <p className="text-sm leading-6 text-slate-400">{status.message}</p>

              <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2.5">
                <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                  MCP endpoint
                </p>
                <p className="mt-1 break-all font-mono text-xs text-slate-300">{status.mcp_url}</p>
              </div>

              {status.connected ? (
                <>
                  {status.tools.length > 0 && (
                    <div>
                      <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                        Available tools
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {status.tools.map((tool) => (
                          <span
                            key={tool}
                            className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-300"
                          >
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleDisconnect()}
                    className="text-xs text-red-400/80 transition hover:text-red-300"
                  >
                    Disconnect Robinhood
                  </button>
                </>
              ) : (
                <>
                  <ul className="list-disc space-y-1 pl-5 text-xs leading-5 text-slate-500">
                    <li>Read portfolio, positions, balances, and quotes</li>
                    <li>Trade only in your dedicated Robinhood Agentic account</li>
                    <li>Authenticate on desktop — Robinhood may require mobile verification</li>
                  </ul>
                  <button
                    type="button"
                    onClick={handleConnect}
                    className="w-full rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200 transition hover:border-emerald-400/50"
                  >
                    Connect Robinhood MCP
                  </button>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
