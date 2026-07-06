import type { KeyboardEvent } from "react";

type SearchBarProps = {
  value: string;
  placeholder: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function SearchBar({ value, placeholder, loading, onChange, onSubmit }: SearchBarProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !loading) onSubmit();
  };

  return (
    <div className="relative">
      <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">
        Probe research agent
      </p>
      <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/80 px-4 py-3 shadow-lg shadow-black/20">
        <input
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={loading}
          className="flex-1 bg-transparent text-base text-slate-100 outline-none placeholder:text-slate-600 disabled:opacity-60"
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          aria-label="Run research"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          ) : (
            <span className="text-lg leading-none">→</span>
          )}
        </button>
      </div>
    </div>
  );
}
