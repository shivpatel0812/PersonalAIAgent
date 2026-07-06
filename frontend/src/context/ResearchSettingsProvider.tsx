import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ResearchSettingsContext,
  type ResearchSettingsContextValue,
} from "./ResearchSettingsContext";
import type { ResearchSettings } from "../types/research";

const STORAGE_KEY = "research-settings";

const DEFAULT_SETTINGS: ResearchSettings = {
  accentColor: "#3b82f6",
  maxSearches: 4,
  placeholder: "Ask anything...",
};

function loadSettings(): ResearchSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

type ResearchSettingsProviderProps = {
  children: ReactNode;
};

export function ResearchSettingsProvider({ children }: ResearchSettingsProviderProps) {
  const [settings, setSettings] = useState<ResearchSettings>(loadSettings);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    document.documentElement.style.setProperty("--accent", settings.accentColor);
  }, [settings]);

  const value = useMemo<ResearchSettingsContextValue>(
    () => ({
      ...settings,
      setAccentColor: (accentColor: string) => setSettings((prev) => ({ ...prev, accentColor })),
      setMaxSearches: (maxSearches: number) =>
        setSettings((prev) => ({ ...prev, maxSearches: Math.min(25, Math.max(1, maxSearches)) })),
      setPlaceholder: (placeholder: string) => setSettings((prev) => ({ ...prev, placeholder })),
    }),
    [settings],
  );

  return (
    <ResearchSettingsContext.Provider value={value}>
      {children}
    </ResearchSettingsContext.Provider>
  );
}
