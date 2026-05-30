"use client";

import type { AnalysisStepLog, AnalysisWorkflowStatus } from "../../app/_lib/api-client";

export const AGENT_STEP_LABELS: Record<string, string> = {
  "01_company_profiling": "企业画像智能体",
  "02_product_understanding": "产品理解智能体",
  "03_data_collection": "数据采集智能体",
  "04_competitor_analysis": "竞品分析智能体",
  "05_market_profiling": "市场画像智能体",
  "06_content_trend": "内容趋势智能体",
  "07_opportunity_scoring": "机会评分智能体",
  "08_marketing_prep": "营销准备智能体",
  "09_report_prep": "报告准备智能体",
};

export const AGENT_NODE_LABELS: Record<string, string> = {
  "01_company_profiling": "企业画像",
  "02_product_understanding": "产品理解",
  "03_data_collection": "数据采集",
  "04_competitor_analysis": "竞品分析",
  "05_market_profiling": "市场画像",
  "06_content_trend": "内容趋势",
  "07_opportunity_scoring": "机会评分",
  "08_marketing_prep": "营销准备",
  "09_report_prep": "报告准备",
};

const AGENT_STEP_DESCRIPTIONS: Record<string, string> = {
  "01_company_profiling": "读取企业地区、产业带、目标市场和出海背景，形成分析上下文。",
  "02_product_understanding": "理解产品名称、品类、材质、认证、价格和关键词信号。",
  "03_data_collection": "汇总 World Bank、GDELT、YouTube、Etsy、UN Comtrade 与 CSV 样本数据。",
  "04_competitor_analysis": "提取竞品价格带、标题关键词、平台表现和差异化线索。",
  "05_market_profiling": "生成目标市场画像，覆盖宏观需求、新闻风险和贸易环境。",
  "06_content_trend": "识别海外内容趋势、搜索意图、社媒话题和素材方向。",
  "07_opportunity_scoring": "计算机会评分、风险提示、推荐排序和下一步动作。",
  "08_marketing_prep": "准备标题、卖点、广告文案、SEO 关键词和本地化提示。",
  "09_report_prep": "整理报告结构、数据来源说明和可跳转的报告入口。",
};

const FALLBACK_TEXT = "该步骤使用本地样本数据保障演示稳定。";

type AgentFlowTimelineProps = {
  steps: AnalysisStepLog[];
  currentStepId?: string | null;
};

export function AgentFlowTimeline({ steps, currentStepId }: AgentFlowTimelineProps) {
  return (
    <div className="grid gap-3">
      {steps.map((step, index) => (
        <AgentFlowStep
          key={step.step_id}
          active={step.step_id === currentStepId}
          index={index + 1}
          step={step}
        />
      ))}
    </div>
  );
}

function AgentFlowStep({
  step,
  index,
  active,
}: {
  step: AnalysisStepLog;
  index: number;
  active: boolean;
}) {
  const fallbackUsed = step.status === "fallback_used" || step.fallback_used;
  const hasError = step.status === "failed";
  const summaryItems = outputSummaryItems(step.output_summary);
  const sourceLabels = step.sources
    .map((source) => formatSource(source))
    .filter((source): source is string => Boolean(source))
    .slice(0, 3);

  return (
    <article
      className={`rounded-lg border bg-white p-4 transition ${
        active ? "border-river/50 shadow-panel ring-2 ring-river/10" : "border-slate-200"
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-md text-sm font-semibold ${numberClassName(step.status)}`}>
            {index}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-ink">
                {AGENT_STEP_LABELS[step.step_id] ?? step.title}
              </h3>
              <span className="text-xs font-medium text-slate-400">{AGENT_NODE_LABELS[step.step_id] ?? step.node}</span>
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              {AGENT_STEP_DESCRIPTIONS[step.step_id] ?? "执行智能体分析节点。"}
            </p>
          </div>
        </div>
        <StatusBadge status={step.status} />
      </div>

      <div className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
        <MetaItem label="开始时间" value={formatDateTime(step.started_at)} />
        <MetaItem label="耗时" value={formatDuration(step.duration_ms)} />
        <MetaItem label="来源" value={sourceLabels.join("；") || "-"} />
      </div>

      {summaryItems.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {summaryItems.map((item) => (
            <span key={item} className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
              {item}
            </span>
          ))}
        </div>
      ) : null}

      {fallbackUsed ? (
        <p className="mt-3 rounded-md border border-wheat/40 bg-wheat/10 px-3 py-2 text-sm leading-6 text-ink">
          {FALLBACK_TEXT}
        </p>
      ) : null}

      {hasError ? (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm leading-6 text-red-700">
          {step.error_message || "该步骤执行失败，请检查后端分析日志。"}
        </p>
      ) : null}
    </article>
  );
}

function StatusBadge({ status }: { status: AnalysisWorkflowStatus }) {
  return (
    <span
      className={`inline-flex w-fit shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${statusClassName(status)}`}
    >
      {statusLabel(status)}
    </span>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-semibold text-slate-400">{label}</p>
      <p className="mt-1 truncate text-slate-600">{value}</p>
    </div>
  );
}

function statusLabel(status: AnalysisWorkflowStatus): string {
  const labels: Record<AnalysisWorkflowStatus, string> = {
    waiting: "等待中",
    running: "运行中",
    success: "已完成",
    failed: "失败",
    fallback_used: "使用兜底",
  };
  return labels[status];
}

function statusClassName(status: AnalysisWorkflowStatus): string {
  const classNames: Record<AnalysisWorkflowStatus, string> = {
    waiting: "bg-slate-100 text-slate-600 ring-slate-200",
    running: "bg-river/10 text-river ring-river/20",
    success: "bg-jade/10 text-jade ring-jade/20",
    failed: "bg-red-50 text-red-700 ring-red-200",
    fallback_used: "bg-wheat/15 text-ink ring-wheat/30",
  };
  return classNames[status];
}

function numberClassName(status: AnalysisWorkflowStatus): string {
  if (status === "success") {
    return "bg-jade/10 text-jade ring-1 ring-jade/20";
  }
  if (status === "running") {
    return "bg-river text-white ring-1 ring-river/20";
  }
  if (status === "fallback_used") {
    return "bg-wheat/15 text-ink ring-1 ring-wheat/30";
  }
  if (status === "failed") {
    return "bg-red-50 text-red-700 ring-1 ring-red-200";
  }
  return "bg-slate-100 text-slate-500 ring-1 ring-slate-200";
}

function outputSummaryItems(summary: Record<string, unknown>): string[] {
  return Object.entries(summary)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 4)
    .map(([key, value]) => `${humanizeKey(key)}：${formatValue(value)}`);
}

function formatSource(source: Record<string, unknown>): string | null {
  const provider = typeof source.provider === "string" ? source.provider : null;
  const label = typeof source.source_label === "string" ? source.source_label : null;
  if (provider && label) {
    return `${provider} / ${label}`;
  }
  return provider ?? label;
}

function humanizeKey(value: string): string {
  const labels: Record<string, string> = {
    company_id: "企业ID",
    company_name: "企业",
    target_country_count: "国家数",
    product_count: "产品数",
    signal_count: "信号数",
    competitor_count: "竞品数",
    market_count: "市场数",
    trend_count: "趋势数",
    item_count: "评分数",
    top_score: "最高分",
    asset_count: "素材数",
    report_id: "报告ID",
    markdown_length: "报告字数",
    ai_fallback_used: "AI兜底",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatValue(value: unknown): string {
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (typeof value === "object" && value !== null) {
    return "已生成";
  }
  return String(value);
}

function formatDuration(value: number | null): string {
  if (value === null) {
    return "-";
  }
  if (value < 1000) {
    return `${value} ms`;
  }
  return `${(value / 1000).toFixed(1)} s`;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
