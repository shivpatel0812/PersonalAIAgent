import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";

type AnswerContentProps = {
  content: string;
};

const markdownComponents: Components = {
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-slate-100">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold text-slate-100">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-semibold text-slate-100">{children}</h4>
  ),
  p: ({ children }) => <p className="text-sm leading-7 text-slate-300">{children}</p>,
  strong: ({ children }) => (
    <strong className="font-semibold text-slate-100">{children}</strong>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-accent underline decoration-accent/40 underline-offset-2 hover:brightness-110"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="list-disc space-y-2 pl-5 text-sm text-slate-300">{children}</ul>,
  ol: ({ children }) => (
    <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-300">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-7">{children}</li>,
};

export function AnswerContent({ content }: AnswerContentProps) {
  return (
    <div className="space-y-4">
      <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
    </div>
  );
}
