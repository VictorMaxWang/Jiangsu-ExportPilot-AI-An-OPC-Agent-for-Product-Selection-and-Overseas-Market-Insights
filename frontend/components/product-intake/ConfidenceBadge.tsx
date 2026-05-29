type ConfidenceBadgeProps = {
  value: string | number | null;
  lowConfidence?: boolean;
};

export function ConfidenceBadge({ value, lowConfidence = false }: ConfidenceBadgeProps) {
  const score = toNumber(value);
  const percentage = score === null ? "待补充" : `${Math.round(score * 100)}%`;
  const level = score === null || score < 0.35 ? "manual" : score < 0.65 || lowConfidence ? "low" : "high";

  const className = {
    high: "bg-jade/10 text-jade ring-jade/20",
    low: "bg-wheat/15 text-ink ring-wheat/30",
    manual: "bg-red-50 text-red-700 ring-red-200",
  }[level];

  const label = {
    high: "AI 置信度较高",
    low: "AI 置信度偏低",
    manual: "需要人工补全",
  }[level];

  return (
    <span className={`inline-flex w-fit items-center rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${className}`}>
      {label} · {percentage}
    </span>
  );
}

function toNumber(value: string | number | null): number | null {
  if (value === null || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
