export type FallbackSource = "csv" | "sample" | "mock" | "public_api" | "cached";

type FallbackNoticeProps = {
  source: FallbackSource;
  title?: string;
  description?: string;
};

const sourceLabels: Record<FallbackSource, string> = {
  csv: "CSV 兜底",
  sample: "样本数据",
  mock: "Mock 输出",
  public_api: "公开 API",
  cached: "缓存结果",
};

export function FallbackNotice({ source, title, description }: FallbackNoticeProps) {
  return (
    <aside className="rounded-lg border border-wheat/40 bg-wheat/10 p-4">
      <p className="text-sm font-semibold text-ink">{title ?? sourceLabels[source]}</p>
      {description ? <p className="mt-2 text-sm leading-6 text-slate-700">{description}</p> : null}
    </aside>
  );
}
