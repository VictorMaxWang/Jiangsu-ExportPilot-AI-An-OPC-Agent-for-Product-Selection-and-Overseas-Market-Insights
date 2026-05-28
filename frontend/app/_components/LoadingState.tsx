type LoadingStateProps = {
  label?: string;
  rows?: number;
};

export function LoadingState({ label = "正在加载演示数据", rows = 3 }: LoadingStateProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <div className="mt-4 grid gap-3" aria-hidden="true">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="h-4 animate-pulse rounded bg-slate-100" />
        ))}
      </div>
    </div>
  );
}
