import { useEffect, useState } from "react";
import {
  deleteMicrosoftAccount,
  fetchMicrosoftAccounts,
  getMicrosoftConnectUrl,
  setPrimaryMicrosoftAccount,
  updateMicrosoftAccountLabel,
  type MicrosoftAccountInfo,
} from "../../lib/api/microsoft";

type MicrosoftAccountsBarProps = {
  refreshKey?: number;
  oauthReturn?: "connected" | "error" | null;
  oauthErrorMessage?: string | null;
};

export function MicrosoftAccountsBar({
  refreshKey = 0,
  oauthReturn = null,
  oauthErrorMessage = null,
}: MicrosoftAccountsBarProps) {
  const [accounts, setAccounts] = useState<MicrosoftAccountInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [editingLabelFor, setEditingLabelFor] = useState<string | null>(null);
  const [labelInput, setLabelInput] = useState("");

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const accountsData = await fetchMicrosoftAccounts();
      setAccounts(accountsData.accounts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Microsoft accounts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (oauthReturn === "error") {
      setError(oauthErrorMessage || "Microsoft sign-in failed. Try again.");
      setLoading(false);
      setExpanded(true);
      return;
    }

    void loadData();
  }, [refreshKey, oauthReturn, oauthErrorMessage]);

  function handleConnectNewAccount(selectAccount = false) {
    sessionStorage.setItem("microsoft_oauth_pending", "1");
    window.location.href = getMicrosoftConnectUrl(selectAccount);
  }

  async function handleDeleteAccount(accountId: string) {
    if (!confirm("Are you sure you want to disconnect this Outlook account?")) return;
    try {
      await deleteMicrosoftAccount(accountId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete account");
    }
  }

  async function handleSetPrimary(accountId: string) {
    try {
      await setPrimaryMicrosoftAccount(accountId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set primary account");
    }
  }

  async function handleSaveLabel(accountId: string) {
    try {
      await updateMicrosoftAccountLabel(accountId, labelInput || null);
      setEditingLabelFor(null);
      setLabelInput("");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update label");
    }
  }

  function startEditingLabel(account: MicrosoftAccountInfo) {
    setEditingLabelFor(account.id);
    setLabelInput(account.account_label || "");
  }

  const countLabel = loading
    ? "Loading…"
    : accounts.length === 0
      ? "Not connected"
      : `${accounts.length} connected`;

  return (
    <div className="border-b border-slate-800 bg-slate-950/80">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-slate-900/60"
      >
        <span className="text-sm text-slate-300">
          Outlook Accounts <span className="text-slate-500">•</span> {countLabel}
        </span>
        <span className={`text-slate-500 transition ${expanded ? "rotate-180" : ""}`}>▾</span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-slate-800 px-4 py-4">
          {error && <p className="text-sm text-red-300">{error}</p>}

          {!loading && accounts.length === 0 && (
            <button
              type="button"
              onClick={() => handleConnectNewAccount()}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition hover:border-sky-500/50"
            >
              Connect Outlook Account
            </button>
          )}

          {accounts.map((account) => (
            <div
              key={account.id}
              className={`rounded-lg border px-3 py-2.5 ${
                account.is_primary
                  ? "border-sky-500/30 bg-sky-500/5"
                  : "border-slate-800 bg-slate-900/60"
              }`}
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">{account.email}</span>
                    {account.is_primary && (
                      <span className="rounded border border-sky-500/30 bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-sky-400">
                        Primary
                      </span>
                    )}
                  </div>

                  {editingLabelFor === account.id ? (
                    <div className="mt-1 flex items-center gap-2">
                      <input
                        type="text"
                        value={labelInput}
                        onChange={(e) => setLabelInput(e.target.value)}
                        placeholder="Label (e.g., Work, Personal)"
                        className="flex-1 rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 focus:border-sky-500/50 focus:outline-none"
                        autoFocus
                      />
                      <button
                        onClick={() => void handleSaveLabel(account.id)}
                        className="text-xs text-sky-400 hover:text-sky-300"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingLabelFor(null)}
                        className="text-xs text-slate-500 hover:text-slate-400"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => startEditingLabel(account)}
                      className="mt-0.5 text-xs text-slate-500 hover:text-slate-300"
                    >
                      {account.account_label || "+ Add label"}
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1">
                  {!account.is_primary && (
                    <button
                      onClick={() => void handleSetPrimary(account.id)}
                      className="rounded px-2 py-1 text-[10px] text-slate-500 transition hover:bg-slate-800 hover:text-slate-300"
                    >
                      Set Primary
                    </button>
                  )}
                  <button
                    onClick={() => void handleDeleteAccount(account.id)}
                    className="rounded px-2 py-1 text-[10px] text-red-400/80 transition hover:bg-red-500/10 hover:text-red-400"
                  >
                    Disconnect
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {account.granted_services.map((serviceName) => (
                  <span
                    key={serviceName}
                    className="rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-400"
                  >
                    {serviceName === "mail" ? "Outlook Mail" : serviceName} ✓
                  </span>
                ))}
              </div>
            </div>
          ))}

          {accounts.length > 0 && (
            <button
              type="button"
              onClick={() => handleConnectNewAccount(true)}
              className="w-full rounded-lg border border-dashed border-slate-700 bg-slate-900/40 px-3 py-2 text-sm text-slate-400 transition hover:border-sky-500/50 hover:text-sky-300"
            >
              + Add Another Account
            </button>
          )}
        </div>
      )}
    </div>
  );
}
