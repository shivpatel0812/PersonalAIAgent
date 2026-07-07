import { useEffect, useState } from "react";
import {
  deleteAccount,
  fetchAccounts,
  fetchAvailableServices,
  setPrimaryAccount,
  updateAccountLabel,
  type AccountInfo,
  type ServiceInfo,
} from "../../lib/api/google";

type GoogleCalendarPanelProps = {
  refreshKey?: number;
};

export function GoogleCalendarPanel({ refreshKey = 0 }: GoogleCalendarPanelProps) {
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const [availableServices, setAvailableServices] = useState<ServiceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingLabelFor, setEditingLabelFor] = useState<string | null>(null);
  const [labelInput, setLabelInput] = useState("");

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [accountsData, servicesData] = await Promise.all([
        fetchAccounts(),
        fetchAvailableServices(),
      ]);
      setAccounts(accountsData.accounts);
      setAvailableServices(servicesData.services);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load accounts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [refreshKey]);

  async function handleDeleteAccount(accountId: string) {
    if (!confirm("Are you sure you want to disconnect this account?")) return;
    try {
      await deleteAccount(accountId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete account");
    }
  }

  async function handleSetPrimary(accountId: string) {
    try {
      await setPrimaryAccount(accountId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set primary account");
    }
  }

  async function handleSaveLabel(accountId: string) {
    try {
      await updateAccountLabel(accountId, labelInput || null);
      setEditingLabelFor(null);
      setLabelInput("");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update label");
    }
  }

  function startEditingLabel(account: AccountInfo) {
    setEditingLabelFor(account.id);
    setLabelInput(account.account_label || "");
  }

  function getServiceLabel(serviceName: string): string {
    const service = availableServices.find(s => s.name === serviceName);
    return service?.label || serviceName;
  }

  function handleConnectNewAccount() {
    // Navigate to OAuth flow
    window.location.href = `${import.meta.env.VITE_API_URL}/auth/google/connect`;
  }

  if (loading) {
    return (
      <section className="mb-4 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
        <p className="text-sm text-slate-500">Loading Google accounts…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
        <p className="text-sm text-red-300">{error}</p>
        <button
          onClick={loadData}
          className="mt-2 text-xs text-red-400 hover:text-red-300"
        >
          Retry
        </button>
      </section>
    );
  }

  return (
    <section className="mb-4 rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-slate-200">Google Accounts</p>
        <button
          type="button"
          onClick={loadData}
          className="text-xs text-slate-500 transition hover:text-slate-300"
        >
          Refresh
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-400">No Google accounts connected</p>
          <button
            type="button"
            onClick={handleConnectNewAccount}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 transition hover:border-accent"
          >
            Connect Google Account
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map(account => (
            <div
              key={account.id}
              className={`rounded-lg border px-3 py-2.5 ${
                account.is_primary
                  ? "border-emerald-500/30 bg-emerald-500/5"
                  : "border-slate-800 bg-slate-900/60"
              }`}
            >
              {/* Account Header */}
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">
                      {account.email}
                    </span>
                    {account.is_primary && (
                      <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-emerald-400">
                        Primary
                      </span>
                    )}
                  </div>

                  {/* Account Label */}
                  {editingLabelFor === account.id ? (
                    <div className="mt-1 flex items-center gap-2">
                      <input
                        type="text"
                        value={labelInput}
                        onChange={e => setLabelInput(e.target.value)}
                        placeholder="Label (e.g., Work, Personal)"
                        className="flex-1 rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 focus:border-accent focus:outline-none"
                        autoFocus
                      />
                      <button
                        onClick={() => handleSaveLabel(account.id)}
                        className="text-xs text-accent hover:text-accent/80"
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
                      onClick={() => handleSetPrimary(account.id)}
                      className="rounded px-2 py-1 text-[10px] text-slate-500 transition hover:bg-slate-800 hover:text-slate-300"
                      title="Set as primary account"
                    >
                      Set Primary
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteAccount(account.id)}
                    className="rounded px-2 py-1 text-[10px] text-red-400/80 transition hover:bg-red-500/10 hover:text-red-400"
                    title="Disconnect account"
                  >
                    Disconnect
                  </button>
                </div>
              </div>

              {/* Services */}
              <div className="flex flex-wrap gap-1.5">
                {account.granted_services.map(serviceName => (
                  <span
                    key={serviceName}
                    className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400"
                  >
                    {getServiceLabel(serviceName)} ✓
                  </span>
                ))}
                {account.granted_services.length === 0 && (
                  <span className="text-xs text-slate-500">No services connected</span>
                )}
              </div>

              {/* Add More Services for this account */}
              {account.granted_services.length < availableServices.length && (
                <button
                  onClick={handleConnectNewAccount}
                  className="mt-2 w-full rounded border border-slate-700 bg-slate-800/50 px-2 py-1 text-xs text-slate-400 transition hover:border-accent/50 hover:text-accent"
                >
                  + Add more services to this account
                </button>
              )}
            </div>
          ))}

          {/* Add Another Account */}
          <button
            type="button"
            onClick={handleConnectNewAccount}
            className="w-full rounded-lg border border-dashed border-slate-700 bg-slate-900/40 px-3 py-2.5 text-sm text-slate-400 transition hover:border-accent hover:text-accent"
          >
            + Add Another Account
          </button>
        </div>
      )}
    </section>
  );
}
