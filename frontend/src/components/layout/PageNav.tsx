import type { PageConfig, PageType } from "../../types/conversation";

export type PersonalSubView = "chat" | "email-agent";

type PageNavProps = {
  pages: PageConfig[];
  activePage: PageType;
  onSelect: (pageType: PageType) => void;
  personalSubView?: PersonalSubView;
  onPersonalSubViewChange?: (view: PersonalSubView) => void;
  emailAgentCount?: number;
};

export function PageNav({
  pages,
  activePage,
  onSelect,
  personalSubView = "chat",
  onPersonalSubViewChange,
  emailAgentCount = 0,
}: PageNavProps) {
  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-950/95 backdrop-blur">
      <div className="border-b border-slate-800 px-4 py-4">
        <p className="text-sm font-medium text-slate-200">Research pages</p>
        <p className="mt-1 text-xs text-slate-500">
          Each page has its own chats. Memory is shared across all of them.
        </p>
      </div>

      <nav className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {pages.map((page) => {
          const isActive = page.type === activePage;
          const isPersonal = page.type === "personal";

          if (isPersonal) {
            return (
              <div key={page.type} className="space-y-1">
                <button
                  type="button"
                  onClick={() => onSelect(page.type)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                    isActive
                      ? "border-accent/50 bg-accent/10"
                      : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
                  }`}
                >
                  <p className="text-sm font-medium text-slate-200">{page.title}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{page.description}</p>
                </button>

                {isActive && onPersonalSubViewChange && (
                  <div className="ml-2 space-y-1 border-l border-slate-800 pl-3">
                    <button
                      type="button"
                      onClick={() => onPersonalSubViewChange("chat")}
                      className={`w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                        personalSubView === "chat"
                          ? "bg-slate-800 text-slate-100"
                          : "text-slate-500 hover:bg-slate-900/60 hover:text-slate-300"
                      }`}
                    >
                      Chat
                    </button>
                    <button
                      type="button"
                      onClick={() => onPersonalSubViewChange("email-agent")}
                      className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                        personalSubView === "email-agent"
                          ? "bg-slate-800 text-slate-100"
                          : "text-slate-500 hover:bg-slate-900/60 hover:text-slate-300"
                      }`}
                    >
                      <span>Email Agent</span>
                      {emailAgentCount > 0 && (
                        <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                          {emailAgentCount}
                        </span>
                      )}
                    </button>
                  </div>
                )}
              </div>
            );
          }

          return (
            <button
              key={page.type}
              type="button"
              onClick={() => onSelect(page.type)}
              className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                isActive
                  ? "border-accent/50 bg-accent/10"
                  : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
              }`}
            >
              <p className="text-sm font-medium text-slate-200">{page.title}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{page.description}</p>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
