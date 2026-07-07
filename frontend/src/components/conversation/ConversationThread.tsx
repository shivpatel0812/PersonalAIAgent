import type { ConversationMessage } from "../../types/conversation";
import { extractSourcesFromSteps } from "../../lib/utils/research";
import { AnswerContent } from "../research/AnswerContent";
import { SourcesPanel } from "../research/SourcesPanel";
import { ReasoningPanel } from "../research/ReasoningPanel";
import type { AgentStep } from "../../types/research";

type MessageBubbleProps = {
  message: ConversationMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const sources = !isUser ? extractSourcesFromSteps(message.steps) : [];

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md border border-accent/30 bg-accent/10 px-4 py-3">
          <p className="text-sm leading-7 text-slate-100">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="max-w-full rounded-2xl rounded-bl-md border border-slate-800 bg-slate-900/50 px-5 py-4">
        <AnswerContent content={message.content} />
      </div>
      {message.steps.length > 0 && (
        <ReasoningPanel steps={message.steps} durationMs={null} loading={false} />
      )}
      {sources.length > 0 && <SourcesPanel sources={sources} />}
    </div>
  );
}

type ConversationThreadProps = {
  messages: ConversationMessage[];
  loadingConversation: boolean;
  isResearching: boolean;
  pendingQuestion: string | null;
  streamingSteps: AgentStep[];
  memoryRunsCount: number;
};

export function ConversationThread({
  messages,
  loadingConversation,
  isResearching,
  pendingQuestion,
  streamingSteps,
}: ConversationThreadProps) {
  if (loadingConversation) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-sm text-slate-500">Loading conversation…</p>
      </div>
    );
  }

  if (messages.length === 0 && !isResearching) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="max-w-md text-center text-sm leading-7 text-slate-500">
          Start a new chat or pick one from the sidebar. Follow-ups stay in this
          chat — related past research still comes from shared memory.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-8 overflow-y-auto px-1 py-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {pendingQuestion && (
        <div className="flex justify-end">
          <div className="max-w-[85%] rounded-2xl rounded-br-md border border-accent/30 bg-accent/10 px-4 py-3">
            <p className="text-sm leading-7 text-slate-100">{pendingQuestion}</p>
          </div>
        </div>
      )}

      {isResearching && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/30 px-4 py-3">
            <p className="text-sm text-slate-400">Researching…</p>
          </div>
          {streamingSteps.length > 0 && (
            <ReasoningPanel steps={streamingSteps} durationMs={null} loading />
          )}
        </div>
      )}
    </div>
  );
}
