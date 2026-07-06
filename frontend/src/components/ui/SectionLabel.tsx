import type { ReactNode } from "react";

type SectionLabelProps = {
  children: ReactNode;
  right?: ReactNode;
};

export function SectionLabel({ children, right }: SectionLabelProps) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500">
        {children}
      </p>
      {right}
    </div>
  );
}
