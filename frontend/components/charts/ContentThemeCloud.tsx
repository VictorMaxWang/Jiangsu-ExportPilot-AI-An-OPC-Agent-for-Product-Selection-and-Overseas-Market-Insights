import type { DashboardContentTheme } from "../../app/_lib/api-client";

type ContentThemeCloudProps = {
  items: DashboardContentTheme[];
};

export function ContentThemeCloud({ items }: ContentThemeCloudProps) {
  const maxWeight = Math.max(...items.map((item) => item.weight), 1);
  return (
    <div className="flex min-h-64 flex-wrap content-center items-center gap-3 rounded-lg bg-slate-50 p-5">
      {items.map((item) => {
        const level = Math.max(0, Math.min(4, Math.round((item.weight / maxWeight) * 4)));
        return (
          <span
            key={`${item.theme}-${item.country ?? "all"}-${item.keyword ?? "keyword"}`}
            className={tagClassName(level)}
            title={`${item.country ?? "ALL"} · ${item.keyword ?? "content trend"}`}
          >
            {item.theme}
          </span>
        );
      })}
    </div>
  );
}

function tagClassName(level: number): string {
  const classNames = [
    "rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600",
    "rounded-md border border-river/20 bg-river/5 px-3 py-1.5 text-sm font-semibold text-river",
    "rounded-md border border-jade/20 bg-jade/10 px-4 py-2 text-base font-semibold text-jade",
    "rounded-md border border-wheat/40 bg-wheat/15 px-4 py-2 text-lg font-semibold text-ink",
    "rounded-md border border-river/30 bg-river px-5 py-2.5 text-xl font-semibold text-white shadow-sm",
  ];
  return classNames[level] ?? classNames[0];
}
