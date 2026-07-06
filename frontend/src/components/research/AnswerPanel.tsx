import { SectionLabel } from "../ui/SectionLabel";
import { AnswerContent } from "./AnswerContent";

type AnswerPanelProps = {
  answer: string;
};

export function AnswerPanel({ answer }: AnswerPanelProps) {
  return (
    <section className="mt-8">
      <SectionLabel>Answer</SectionLabel>
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 px-5 py-5">
        <AnswerContent content={answer} />
      </div>
    </section>
  );
}
