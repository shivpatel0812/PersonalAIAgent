import { createContext, useContext } from "react";
import type { ResearchSettings } from "../types/research";

export type ResearchSettingsContextValue = ResearchSettings & {
  setAccentColor: (color: string) => void;
  setMaxSearches: (value: number) => void;
  setPlaceholder: (value: string) => void;
};

export const ResearchSettingsContext = createContext<ResearchSettingsContextValue | null>(
  null,
);

export function useResearchSettings(): ResearchSettingsContextValue {
  const context = useContext(ResearchSettingsContext);
  if (!context) {
    throw new Error("useResearchSettings must be used within ResearchSettingsProvider");
  }
  return context;
}
