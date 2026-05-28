type MetricTrend = {
  value: string;
  tone: "positive" | "negative" | "neutral";
};

type MetricCardProps = {
  label: string;
  value: string | number;
  helperText?: string;
  trend?: MetricTrend;
};

const trendClassNames: Record<MetricTrend["tone"], string> = {
  positive: "text-jade",
  negative: "text-red-700",
  neutral: "text-slate-500",
};

export function MetricCard({ label, value, helperText, trend }: MetricCardProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <div className="mt-3 flex items-end justify-between gap-3">
        <p className="text-3xl font-semibold text-ink">{value}</p>
        {trend ? (
          <p className={`pb-1 text-xs font-semibold ${trendClassNames[trend.tone]}`}>
            {trend.value}
          </p>
        ) : null}
      </div>
      {helperText ? <p className="mt-3 text-xs leading-5 text-slate-500">{helperText}</p> : null}
    </section>
  );
}
