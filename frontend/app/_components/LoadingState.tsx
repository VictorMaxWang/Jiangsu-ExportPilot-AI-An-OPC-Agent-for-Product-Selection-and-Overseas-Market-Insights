type LoadingStateProps = {
  label?: string;
  rows?: number;
};

export function LoadingState({ label = "正在加载演示数据", rows = 3 }: LoadingStateProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel" role="status" aria-live="polite">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="mt-4 grid gap-3" aria-hidden="true">
        {Array.from({ length: rows }).map((_, index) => (
          <div
            key={index}
            className={`h-4 animate-pulse rounded bg-slate-100 ${index % 3 === 0 ? "w-full" : index % 3 === 1 ? "w-5/6" : "w-2/3"}`}
          />
        ))}
      </div>
    </div>
  );
}
