"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import { MetricCard } from "../../_components/MetricCard";
import { PageHeader } from "../../_components/PageHeader";
import { SuccessState } from "../../_components/SuccessState";
import { useI18n } from "../../_components/LanguageProvider";
import {
  DashboardResponse,
  Report,
  generateReport,
  getDashboard,
  getFriendlyErrorMessage,
  listReports,
} from "../../_lib/api-client";

type ReportsWorkspaceProps = {
  initialAnalysisId: string;
};

type TextFn = (zh: string, en?: string) => string;

export function ReportsWorkspace({ initialAnalysisId }: ReportsWorkspaceProps) {
  const { text } = useI18n();
  const [analysisIdInput, setAnalysisIdInput] = useState(initialAnalysisId);
  const [activeAnalysisId, setActiveAnalysisId] = useState<number | null>(parseAnalysisId(initialAnalysisId));
  const [reports, setReports] = useState<Report[]>([]);
  const [total, setTotal] = useState(0);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [copiedReportId, setCopiedReportId] = useState<number | null>(null);

  const loadReports = useCallback(async (analysisId: number | null) => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const reportResponse = await listReports(analysisId ?? undefined);
      setReports(reportResponse.items);
      setTotal(reportResponse.total);
      if (analysisId) {
        try {
          setDashboard(await getDashboard(analysisId));
        } catch {
          setDashboard(null);
        }
      } else {
        setDashboard(null);
      }
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
      setReports([]);
      setTotal(0);
      setDashboard(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReports(activeAnalysisId);
  }, [activeAnalysisId, loadReports]);

  const fallbackUsed = useMemo(() => {
    if (!dashboard) {
      return false;
    }
    return (
      dashboard.data_sources_used.some((source) => source.fallback_used) ||
      dashboard.top_recommendations.some((item) => item.fallback_used || item.ai_fallback_used)
    );
  }, [dashboard]);

  function handleFilterSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = parseAnalysisId(analysisIdInput);
    if (analysisIdInput.trim() && !parsed) {
      setError("请输入有效的正整数分析 ID。");
      return;
    }
    setActiveAnalysisId(parsed);
  }

  async function handleGenerate(forceRegenerate: boolean) {
    if (!activeAnalysisId) {
      setError("生成报告前请先输入分析 ID。");
      return;
    }
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const report = await generateReport({
        analysis_id: activeAnalysisId,
        force_regenerate: forceRegenerate,
      });
      setNotice(forceRegenerate ? "报告已重新生成。" : "报告已生成。");
      await loadReports(activeAnalysisId);
      setCopiedReportId(null);
      if (!reports.some((item) => item.id === report.id)) {
        setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
      }
    } catch (requestError) {
      setError(withReportRetryMessage(getFriendlyErrorMessage(requestError)));
    } finally {
      setGenerating(false);
    }
  }

  async function copyMarkdown(report: Report) {
    try {
      await navigator.clipboard.writeText(report.content_markdown ?? "");
      setCopiedReportId(report.id);
      window.setTimeout(() => setCopiedReportId((current) => (current === report.id ? null : current)), 2000);
    } catch {
      setError("复制到剪贴板失败，请打开报告并手动选择 Markdown 复制。");
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <PageHeader
          eyebrow="出海交付物"
          eyebrowEn="Export Deliverables"
          title="报告"
          titleEn="Reports"
          description="生成和复核结构化出海选品报告，包含数据源说明、评分上下文、营销草稿和风险边界。"
          descriptionEn="Generate and review structured overseas product-selection reports with data-source notes, scoring context, marketing drafts, and risk limits."
        />
        <div className="flex shrink-0 flex-wrap gap-2">
          {activeAnalysisId ? (
            <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href={`/dashboard/${activeAnalysisId}`}>
              返回看板
            </Link>
          ) : null}
          <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href="/analysis/run">
            运行分析
          </Link>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_auto]">
        <form className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-panel sm:grid-cols-[1fr_auto]" onSubmit={handleFilterSubmit}>
          <label className="grid gap-2">
            <span className="text-sm font-medium text-slate-700">分析 ID</span>
            <input
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
              placeholder="可选，例如 1"
              value={analysisIdInput}
              onChange={(event) => setAnalysisIdInput(event.target.value)}
            />
          </label>
          <button className="self-end rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white" type="submit">
            加载报告
          </button>
        </form>
        <div className="flex flex-wrap items-end gap-2">
          <button
            className="rounded-md bg-jade px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!activeAnalysisId || generating}
            type="button"
            onClick={() => void handleGenerate(false)}
          >
            {generating ? "生成中" : "生成"}
          </button>
          <button
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={!activeAnalysisId || generating}
            type="button"
            onClick={() => void handleGenerate(true)}
          >
            重新生成
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="报告数" value={total} helperText={activeAnalysisId ? `分析 #${activeAnalysisId}` : "全部报告"} />
        <MetricCard label="最高推荐国家" value={dashboard?.country_scores[0]?.country ?? "-"} helperText="来自看板聚合结果" />
        <MetricCard label="最高分" value={formatScore(dashboard?.top_recommendations[0]?.total_score)} helperText="后端评分结果" />
        <MetricCard label="来源数" value={dashboard?.data_sources_used.length ?? "-"} helperText="API、样本与兜底标签" />
      </div>

      <div className="mt-5 grid gap-4">
        <FallbackNotice
          source="sample"
          title="报告证据边界"
          description="报告仅基于结构化分析数据。平台竞品样本只表示价格区间和内容方向，不代表真实销量。"
        />
        {fallbackUsed ? (
          <FallbackNotice
            source="csv"
            title="包含兜底证据"
            description="部分数据源或 AI 步骤使用了兜底数据。发布商品或做投资决策前，请复核实时平台证据。"
          />
        ) : null}
        {notice ? (
          <SuccessState
            title={notice}
            description={text(
              "报告列表已同步更新，可继续查看、复制或返回看板复核来源。",
              "The report list is updated. You can view, copy, or return to the dashboard to verify sources.",
            )}
          />
        ) : null}
        {error ? <ErrorState message={error} /> : null}
      </div>

      <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-ink">报告列表</h2>
            <p className="mt-1 text-sm text-slate-500">
              {text(
                "优先查看 HTML/Markdown 报告；PDF 状态以徽章展示，避免遮挡主要操作。",
                "HTML/Markdown reports are primary; PDF status is shown as a badge so the main actions stay clear.",
              )}
            </p>
          </div>
          {activeAnalysisId ? <span className="rounded-md bg-river/10 px-2.5 py-1 text-xs font-semibold text-river">analysis_id = {activeAnalysisId}</span> : null}
        </div>
        <div className="mt-4">
          {loading ? (
            <LoadingState label="正在加载报告" rows={5} />
          ) : reports.length === 0 ? (
            <EmptyState
              title="暂无报告"
              description={activeAnalysisId ? "可为该分析生成报告，或等待分析工作流完成。" : "请输入分析 ID，或运行一次分析来创建报告。"}
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
                    {text("运行分析", "Run analysis")}
                  </Link>
                  <Link className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-ink" href="/products/import">
                    {text("智能导入", "Smart intake")}
                  </Link>
                </div>
              }
            />
          ) : (
            <div className="grid gap-3">
              {reports.map((report) => (
                <ReportCard
                  key={report.id}
                  copied={copiedReportId === report.id}
                  report={report}
                  text={text}
                  onCopy={() => void copyMarkdown(report)}
                />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function ReportCard({ report, copied, text, onCopy }: { report: Report; copied: boolean; text: TextFn; onCopy: () => void }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 text-base font-semibold text-ink">{report.title}</h3>
            <AssetBadge label={report.pdf_url ? text("PDF 已就绪", "PDF ready") : text("PDF 部署版开启", "PDF in deployment")} tone={report.pdf_url ? "ready" : "pending"} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            报告 #{report.id} · 分析 #{report.analysis_id} · {formatDate(report.created_at)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
            <AssetBadge label={`Markdown ${report.content_markdown ? text("已生成", "ready") : text("缺失", "missing")}`} tone={report.content_markdown ? "ready" : "missing"} />
            <AssetBadge label={`HTML ${report.content_html ? text("已生成", "ready") : text("缺失", "missing")}`} tone={report.content_html ? "ready" : "missing"} />
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link className="rounded-md bg-river px-3 py-2 text-sm font-semibold text-white" href={`/reports/${report.id}`}>
            {text("查看", "View")}
          </Link>
          <button className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700" type="button" onClick={onCopy}>
            {copied ? text("已复制", "Copied") : text("复制 Markdown", "Copy Markdown")}
          </button>
          <Link className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700" href={`/dashboard/${report.analysis_id}`}>
            {text("看板", "Dashboard")}
          </Link>
        </div>
      </div>
    </article>
  );
}

function AssetBadge({ label, tone }: { label: string; tone: "ready" | "pending" | "missing" }) {
  const className =
    tone === "ready"
      ? "bg-jade/10 text-jade ring-jade/20"
      : tone === "pending"
        ? "bg-wheat/15 text-ink ring-wheat/30"
        : "bg-slate-100 text-slate-500 ring-slate-200";
  return <span className={`rounded-md px-2 py-1 text-xs font-semibold ring-1 ${className}`}>{label}</span>;
}

function parseAnalysisId(value: string): number | null {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function formatScore(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(1) : String(value);
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function withReportRetryMessage(message: string): string {
  return message.includes("可重新生成报告") ? message : `报告生成失败，可重新生成报告。${message}`;
}
