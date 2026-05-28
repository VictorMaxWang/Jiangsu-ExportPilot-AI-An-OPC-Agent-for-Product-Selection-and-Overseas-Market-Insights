import type { ReactNode } from "react";
import { EmptyState } from "../../app/_components/EmptyState";

type ChartPanelProps = {
  title: string;
  description?: string;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  sourceNote?: string;
  badge?: ReactNode;
  children: ReactNode;
};

export function ChartPanel({
  title,
  description,
  isEmpty = false,
  emptyTitle = "暂无图表数据",
  emptyDescription = "当前分析结果未生成该图表所需的数据。",
  sourceNote,
  badge,
  children,
}: ChartPanelProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          {description ? <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p> : null}
        </div>
        {badge ? <div className="shrink-0">{badge}</div> : null}
      </div>
      <div className="mt-4">
        {isEmpty ? <EmptyState title={emptyTitle} description={emptyDescription} /> : children}
      </div>
      {sourceNote ? (
        <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
          {sourceNote}
        </p>
      ) : null}
    </section>
  );
}
