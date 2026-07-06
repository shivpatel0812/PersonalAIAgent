import type { KeyboardEvent } from "react";

type ConversationInputProps = {
  value: string;
  placeholder: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function ConversationInput({
  value,
  placeholder,
  loading,
  onChange,
  onSubmit,
}: ConversationInputProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !loading) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="border-t border-slate-800 bg-[#070b14]/95 px-1 py-4 backdrop-blur">
      <div className="flex items-end gap-3 rounded-xl border border-slate-800 bg-slate-900/80 px-4 py-3 shadow-lg shadow-black/20">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={loading}
          rows={2}
          className="max-h-40 min-h-[3rem] flex-1 resize-y bg-transparent text-base text-slate-100 outline-none placeholder:text-slate-600 disabled:opacity-60"
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          aria-label="Send message"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          ) : (
            <span className="text-lg leading-none">→</span>
          )}
        </button>
      </div>
      <p className="mt-2 text-center text-[11px] text-slate-600">
        Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
