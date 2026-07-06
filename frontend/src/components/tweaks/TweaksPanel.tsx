import { useState } from "react";
import { useResearchSettings } from "../../context/ResearchSettingsContext";

export function TweaksPanel() {
  const [open, setOpen] = useState(false);
  const {
    accentColor,
    maxSearches,
    placeholder,
    setAccentColor,
    setMaxSearches,
    setPlaceholder,
  } = useResearchSettings();

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open tweaks"
          className="fixed right-0 top-1/2 z-30 -translate-y-1/2 rounded-l-lg border border-r-0 border-slate-700 bg-slate-900/95 px-2 py-4 text-xs font-medium text-slate-400 shadow-lg backdrop-blur transition hover:border-accent hover:text-slate-200"
        >
          <span className="[writing-mode:vertical-rl] rotate-180">Tweaks</span>
        </button>
      )}

      {open && (
        <button
          type="button"
          aria-label="Close tweaks"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-30 bg-black/20"
        />
      )}

      <aside
        className={`fixed right-0 top-0 z-40 flex h-screen w-72 flex-col border-l border-slate-800 bg-slate-950/95 backdrop-blur transition-transform duration-300 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-4">
          <p className="text-sm font-medium text-slate-200">Tweaks</p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close tweaks panel"
            className="rounded-lg border border-slate-700 px-2 py-1 text-xs text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-xs text-slate-500">accent</span>
              <input
                type="color"
                value={accentColor}
                onChange={(event) => setAccentColor(event.target.value)}
                className="h-8 w-full cursor-pointer rounded border border-slate-700 bg-slate-950"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs text-slate-500">maxSearches</span>
              <input
                type="number"
                min={1}
                max={25}
                value={maxSearches}
                onChange={(event) => setMaxSearches(Number(event.target.value))}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-accent"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs text-slate-500">placeholder</span>
              <input
                type="text"
                value={placeholder}
                onChange={(event) => setPlaceholder(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 outline-none focus:border-accent"
              />
            </label>
          </div>
        </div>
      </aside>
    </>
  );
}
