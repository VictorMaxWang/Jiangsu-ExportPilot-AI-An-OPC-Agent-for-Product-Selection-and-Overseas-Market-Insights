"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import { MetricCard } from "../../_components/MetricCard";
import { PageHeader } from "../../_components/PageHeader";
import { SuccessState } from "../../_components/SuccessState";
import {
  DashboardResponse,
  Report,
  ReportVersion,
  generateReport,
  getDashboard,
  getFriendlyErrorMessage,
  getReport,
  listReportVersions,
  restoreReportVersion,
} from "../../_lib/api-client";

type ReportDetailWorkspaceProps = {
  reportId: number;
};

const REPORT_VERSION_UPDATED_EVENT = "report-version-updated";

export function ReportDetailWorkspace({ reportId }: ReportDetailWorkspaceProps) {
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [restoringVersionId, setRestoringVersionId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const loadReport = useMemo(() => {
    return async (signal?: AbortSignal, options: { showLoading?: boolean } = {}) => {
      if (options.showLoading ?? true) {
        setLoading(true);
      }
      setError(null);
      try {
        const reportResponse = await getReport(reportId, signal);
        setReport(reportResponse);
        try {
          const versionResponse = await listReportVersions(reportId, signal);
          setVersions(versionResponse.items);
        } catch {
          setVersions([]);
        }
        try {
          setDashboard(await getDashboard(reportResponse.analysis_id, signal));
        } catch {
          setDashboard(null);
        }
      } catch (requestError) {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError(getFriendlyErrorMessage(requestError));
        setReport(null);
        setVersions([]);
        setDashboard(null);
      } finally {
        if (options.showLoading ?? true) {
          setLoading(false);
        }
      }
    };
  }, [reportId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadReport(controller.signal, { showLoading: true });
    return () => controller.abort();
  }, [loadReport]);

  useEffect(() => {
    function handleVersionUpdated(event: Event) {
      const detail = event instanceof CustomEvent ? event.detail : null;
      if (detail && typeof detail.report_id === "number" && detail.report_id !== reportId) {
        return;
      }
      void loadReport(undefined, { showLoading: false });
    }
    window.addEventListener(REPORT_VERSION_UPDATED_EVENT, handleVersionUpdated);
    return () => window.removeEventListener(REPORT_VERSION_UPDATED_EVENT, handleVersionUpdated);
  }, [loadReport, reportId]);

  const fallbackUsed = useMemo(() => {
    if (!dashboard) {
      return false;
    }
    return (
      dashboard.data_sources_used.some((source) => source.fallback_used) ||
      dashboard.top_recommendations.some((item) => item.fallback_used || item.ai_fallback_used)
    );
  }, [dashboard]);

  async function copyMarkdown() {
    if (!report?.content_markdown) {
      return;
    }
    try {
      await navigator.clipboard.writeText(report.content_markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("复制到剪贴板失败，请手动选择 Markdown 内容复制。");
    }
  }

  async function regenerateReport() {
    if (!report) {
      return;
    }
    setRegenerating(true);
    setError(null);
    setNotice(null);
    try {
      const regenerated = await generateReport({
        analysis_id: report.analysis_id,
        force_regenerate: true,
      });
      setReport(regenerated);
      setNotice("报告已重新生成。");
      if (regenerated.id !== report.id) {
        router.push(`/reports/${regenerated.id}`);
      }
    } catch (requestError) {
      setError(withReportRetryMessage(getFriendlyErrorMessage(requestError)));
    } finally {
      setRegenerating(false);
    }
  }

  async function restoreVersion(version: ReportVersion) {
    if (!report || restoringVersionId) {
      return;
    }
    setRestoringVersionId(version.id);
    setError(null);
    setNotice(null);
    try {
      const restored = await restoreReportVersion(report.id, version.id, {
        reason: `Restore report version ${version.version_number}.`,
      });
      setReport(restored.report);
      setNotice(`已恢复到 v${version.version_number}，并保存为新版本 v${restored.version.version_number}。`);
      await loadReport(undefined, { showLoading: false });
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setRestoringVersionId(null);
    }
  }

  if (loading) {
    return (
      <div>
        <PageHeader
          eyebrow="出海报告"
          eyebrowEn="Export Report"
          title={`报告 #${reportId}`}
          titleEn={`Report #${reportId}`}
          description="正在加载已生成的报告内容和看板上下文。"
          descriptionEn="Loading generated report content and dashboard context."
        />
        <LoadingState label="正在加载报告" rows={8} />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader
          eyebrow="出海报告"
          eyebrowEn="Export Report"
          title={`报告 #${reportId}`}
          titleEn={`Report #${reportId}`}
          description="报告详情页只读取已保存的报告内容。"
          descriptionEn="The report viewer reads persisted report content only."
        />
        <ErrorState message={error} />
      </div>
    );
  }

  if (!report) {
    return (
      <EmptyState
        title="未找到报告"
        description="请从报告列表打开一个已存在的报告。"
        action={
          <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/reports">
            返回报告列表
          </Link>
        }
      />
    );
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <PageHeader
          eyebrow="出海报告"
          eyebrowEn="Export Report"
          title={report.title}
          description={`报告 #${report.id} · 分析 #${report.analysis_id}`}
          descriptionEn={`Report #${report.id} · Analysis #${report.analysis_id}`}
        />
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href={`/reports?analysis_id=${report.analysis_id}`}>
            返回列表
          </Link>
          <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href={`/dashboard/${report.analysis_id}`}>
            返回看板
          </Link>
          <button className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300" disabled={!report.content_markdown} type="button" onClick={() => void copyMarkdown()}>
            {copied ? "已复制" : "复制 Markdown"}
          </button>
          <button
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={regenerating}
            type="button"
            onClick={() => void regenerateReport()}
          >
            {regenerating ? "重新生成中" : "重新生成报告"}
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="最高推荐国家" value={dashboard?.country_scores[0]?.country ?? "-"} helperText="来自看板聚合结果" />
        <MetricCard label="最高分" value={formatScore(dashboard?.top_recommendations[0]?.total_score)} helperText="后端评分结果" />
        <MetricCard label="来源数" value={dashboard?.data_sources_used.length ?? "-"} helperText="API、样本与兜底标签" />
        <MetricCard label="PDF" value={report.pdf_url ? "已就绪" : "部署版开启"} helperText="当前优先交付 HTML/Markdown；PDF 状态仅作为能力提示。" />
      </div>

      {notice ? <div className="mt-5"><SuccessState title={notice} description="新报告已保存，可继续复制 Markdown 或返回看板复核来源。" /></div> : null}

      <div className="mt-5 grid gap-4">
        <FallbackNotice
          source="sample"
          title="报告证据边界"
          description="报告基于结构化分析结果。竞品样本不代表真实销量。"
        />
        {fallbackUsed ? (
          <FallbackNotice
            source="csv"
            title="包含兜底证据"
            description="做正式投放决策前，请复核实时平台数据。"
          />
        ) : null}
      </div>

      <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        <div className="mb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-ink">版本列表</h2>
              <p className="mt-1 text-sm text-slate-500">应用聊天修改或恢复旧版本都会追加一个新版本，原版本保留。</p>
            </div>
            <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
              current_version_id = {report.current_version_id ?? "-"}
            </span>
          </div>
          <div className="mt-3 grid gap-2">
            {versions.length === 0 ? (
              <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">暂无版本记录。</p>
            ) : (
              versions.map((version) => {
                const current = version.id === report.current_version_id;
                return (
                  <div key={version.id} className="flex flex-col gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-ink">v{version.version_number}</span>
                        <VersionBadge label={version.source_type} />
                        {current ? <VersionBadge label="当前版本" tone="current" /> : null}
                      </div>
                      <p className="mt-1 text-xs leading-5 text-slate-500">
                        {formatDate(version.created_at)} · {version.version_note || "无版本说明"}
                      </p>
                    </div>
                    <button
                      className="shrink-0 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                      disabled={current || restoringVersionId !== null}
                      type="button"
                      onClick={() => void restoreVersion(version)}
                    >
                      {restoringVersionId === version.id ? "恢复中" : "恢复此版本"}
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>
        {report.content_html ? (
          <div dangerouslySetInnerHTML={{ __html: report.content_html }} />
        ) : report.content_markdown ? (
          <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-700">{report.content_markdown}</pre>
        ) : (
          <EmptyState title="报告内容为空" description="请从报告列表重新生成该报告。" />
        )}
      </section>
    </div>
  );
}

function VersionBadge({ label, tone = "default" }: { label: string; tone?: "default" | "current" }) {
  const className = tone === "current" ? "bg-jade/10 text-jade ring-jade/20" : "bg-white text-slate-600 ring-slate-200";
  return <span className={`rounded-md px-2 py-1 text-xs font-semibold ring-1 ${className}`}>{label}</span>;
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
