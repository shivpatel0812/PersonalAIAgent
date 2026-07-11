import { useState, type FormEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { isSupabaseConfigured } from "../lib/supabase";

export function LoginPage() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isSupabaseConfigured) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#070b14] px-4">
        <div className="max-w-md rounded-2xl border border-slate-800 bg-slate-950/80 p-8 text-center">
          <h1 className="text-xl font-semibold text-slate-100">Auth not configured</h1>
          <p className="mt-3 text-sm text-slate-400">
            Set <code className="text-slate-300">VITE_SUPABASE_URL</code> and{" "}
            <code className="text-slate-300">VITE_SUPABASE_ANON_KEY</code> to enable login.
          </p>
        </div>
      </div>
    );
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setSubmitting(true);
    try {
      if (mode === "signin") {
        await signIn(email.trim(), password);
      } else {
        await signUp(email.trim(), password);
        setInfo(
          "Account created. If email confirmation is enabled in Supabase, check your inbox before signing in.",
        );
        setMode("signin");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#070b14] px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-950/80 p-8 shadow-xl">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
          Personal AI Agent
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-100">
          {mode === "signin" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Use your email and password. Auth is powered by Supabase.
        </p>

        <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4">
          <label className="block">
            <span className="text-xs font-medium text-slate-400">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent/60"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-400">Password</span>
            <input
              type="password"
              required
              minLength={6}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent/60"
            />
          </label>

          {error && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
              {error}
            </p>
          )}
          {info && (
            <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
              {info}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-accent/90 disabled:opacity-50"
          >
            {submitting ? "Please wait…" : mode === "signin" ? "Sign in" : "Sign up"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode((m) => (m === "signin" ? "signup" : "signin"));
            setError(null);
            setInfo(null);
          }}
          className="mt-4 w-full text-center text-sm text-slate-400 transition hover:text-slate-200"
        >
          {mode === "signin"
            ? "Need an account? Sign up"
            : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
