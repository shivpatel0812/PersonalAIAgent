import type { PageConfig, PageType } from "../../types/conversation";

type PageNavProps = {
  pages: PageConfig[];
  activePage: PageType;
  onSelect: (pageType: PageType) => void;
};

export function PageNav({ pages, activePage, onSelect }: PageNavProps) {
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
