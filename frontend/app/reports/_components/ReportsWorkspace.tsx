"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import { MetricCard } from "../../_components/MetricCard";
import { PageHeader } from "../../_components/PageHeader";
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

export function ReportsWorkspace({ initialAnalysisId }: ReportsWorkspaceProps) {
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
      setError("Enter a valid positive analysis id.");
      return;
    }
    setActiveAnalysisId(parsed);
  }

  async function handleGenerate(forceRegenerate: boolean) {
    if (!activeAnalysisId) {
      setError("Enter an analysis id before generating a report.");
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
      setNotice(forceRegenerate ? "Report regenerated." : "Report generated.");
      await loadReports(activeAnalysisId);
      setCopiedReportId(null);
      if (!reports.some((item) => item.id === report.id)) {
        setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
      }
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
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
      setError("Clipboard copy failed. Open the report and select the Markdown manually.");
    }
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <PageHeader
          eyebrow="Export deliverables"
          title="Reports"
          description="Generate and review structured overseas product-selection reports with data-source notes, scoring context, marketing drafts, and risk limits."
        />
        <div className="flex shrink-0 flex-wrap gap-2">
          {activeAnalysisId ? (
            <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href={`/dashboard/${activeAnalysisId}`}>
              Back to dashboard
            </Link>
          ) : null}
          <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href="/analysis/run">
            Run analysis
          </Link>
        </div>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_auto]">
        <form className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-panel sm:grid-cols-[1fr_auto]" onSubmit={handleFilterSubmit}>
          <label className="grid gap-2">
            <span className="text-sm font-medium text-slate-700">Analysis ID</span>
            <input
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
              placeholder="Optional, for example 1"
              value={analysisIdInput}
              onChange={(event) => setAnalysisIdInput(event.target.value)}
            />
          </label>
          <button className="self-end rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white" type="submit">
            Load reports
          </button>
        </form>
        <div className="flex flex-wrap items-end gap-2">
          <button
            className="rounded-md bg-jade px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!activeAnalysisId || generating}
            type="button"
            onClick={() => void handleGenerate(false)}
          >
            {generating ? "Generating" : "Generate"}
          </button>
          <button
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={!activeAnalysisId || generating}
            type="button"
            onClick={() => void handleGenerate(true)}
          >
            Regenerate
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Reports" value={total} helperText={activeAnalysisId ? `Analysis #${activeAnalysisId}` : "All reports"} />
        <MetricCard label="Top country" value={dashboard?.country_scores[0]?.country ?? "-"} helperText="From dashboard aggregation" />
        <MetricCard label="Top score" value={formatScore(dashboard?.top_recommendations[0]?.total_score)} helperText="Backend scoring result" />
        <MetricCard label="Sources" value={dashboard?.data_sources_used.length ?? "-"} helperText="API, sample, and fallback labels" />
      </div>

      <div className="mt-5 grid gap-4">
        <FallbackNotice
          source="sample"
          title="Report evidence boundary"
          description="Reports are based on structured analysis data only. Platform competitor samples indicate price ranges and content direction; they do not represent real sales."
        />
        {fallbackUsed ? (
          <FallbackNotice
            source="csv"
            title="Fallback evidence included"
            description="Some provider or AI steps used fallback data. Review live marketplace evidence before publishing listings or investment decisions."
          />
        ) : null}
        {notice ? <p className="rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
        {error ? <ErrorState message={error} /> : null}
      </div>

      <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-ink">Report list</h2>
          {activeAnalysisId ? <span className="text-sm text-slate-500">Filtered by analysis #{activeAnalysisId}</span> : null}
        </div>
        <div className="mt-4">
          {loading ? (
            <LoadingState label="Loading reports" rows={5} />
          ) : reports.length === 0 ? (
            <EmptyState
              title="No reports found"
              description={activeAnalysisId ? "Generate a report for this analysis or wait for the analysis workflow to finish." : "Enter an analysis id or run an analysis to create reports."}
              action={
                <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
                  Run analysis
                </Link>
              }
            />
          ) : (
            <div className="grid gap-3">
              {reports.map((report) => (
                <ReportCard
                  key={report.id}
                  copied={copiedReportId === report.id}
                  report={report}
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

function ReportCard({ report, copied, onCopy }: { report: Report; copied: boolean; onCopy: () => void }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-ink">{report.title}</h3>
          <p className="mt-1 text-sm text-slate-500">
            Report #{report.id} · Analysis #{report.analysis_id} · {formatDate(report.created_at)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
            <span className="rounded-md bg-white px-2 py-1 text-slate-600">Markdown {report.content_markdown ? "ready" : "missing"}</span>
            <span className="rounded-md bg-white px-2 py-1 text-slate-600">HTML {report.content_html ? "ready" : "missing"}</span>
            <span className="rounded-md bg-white px-2 py-1 text-slate-600">PDF {report.pdf_url ? "ready" : "pending"}</span>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link className="rounded-md bg-river px-3 py-2 text-sm font-semibold text-white" href={`/reports/${report.id}`}>
            View
          </Link>
          <button className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700" type="button" onClick={onCopy}>
            {copied ? "Copied" : "Copy Markdown"}
          </button>
          <Link className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700" href={`/dashboard/${report.analysis_id}`}>
            Dashboard
          </Link>
          <button className="cursor-not-allowed rounded-md border border-slate-200 bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-400" disabled type="button">
            PDF pending
          </button>
        </div>
      </div>
    </article>
  );
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
