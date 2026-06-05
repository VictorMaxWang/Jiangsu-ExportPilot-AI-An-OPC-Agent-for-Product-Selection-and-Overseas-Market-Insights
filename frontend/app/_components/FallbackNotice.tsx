export type FallbackSource = "csv" | "sample" | "mock" | "public_api" | "cached" | "url" | "screenshot" | "ai";

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
  url: "链接解析",
  screenshot: "截图分析",
  ai: "AI 识别",
};

export function FallbackNotice({ source, title, description }: FallbackNoticeProps) {
  return (
    <aside className="rounded-lg border border-wheat/40 bg-wheat/10 p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-white/80 px-2 py-1 text-xs font-semibold text-ink ring-1 ring-wheat/30">
          {sourceLabels[source]}
        </span>
        <p className="text-sm font-semibold text-ink">{title ?? sourceLabels[source]}</p>
      </div>
      {description ? <p className="mt-2 text-sm leading-6 text-slate-700">{description}</p> : null}
    </aside>
  );
}
