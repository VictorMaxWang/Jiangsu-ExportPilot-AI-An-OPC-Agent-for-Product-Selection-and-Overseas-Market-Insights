"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import { MetricCard } from "../../_components/MetricCard";
import { PageHeader } from "../../_components/PageHeader";
import {
  DashboardResponse,
  Report,
  getDashboard,
  getFriendlyErrorMessage,
  getReport,
} from "../../_lib/api-client";

type ReportDetailWorkspaceProps = {
  reportId: number;
};

export function ReportDetailWorkspace({ reportId }: ReportDetailWorkspaceProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function loadReport() {
      setLoading(true);
      setError(null);
      try {
        const reportResponse = await getReport(reportId, controller.signal);
        setReport(reportResponse);
        try {
          setDashboard(await getDashboard(reportResponse.analysis_id, controller.signal));
        } catch {
          setDashboard(null);
        }
      } catch (requestError) {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError(getFriendlyErrorMessage(requestError));
        setReport(null);
        setDashboard(null);
      } finally {
        setLoading(false);
      }
    }

    void loadReport();
    return () => controller.abort();
  }, [reportId]);

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
      setError("Clipboard copy failed. Select the Markdown manually and copy it.");
    }
  }

  if (loading) {
    return (
      <div>
        <PageHeader
          eyebrow="Export report"
          title={`Report #${reportId}`}
          description="Loading generated report content and dashboard context."
        />
        <LoadingState label="Loading report" rows={8} />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader
          eyebrow="Export report"
          title={`Report #${reportId}`}
          description="The report viewer reads persisted report content only."
        />
        <ErrorState message={error} />
      </div>
    );
  }

  if (!report) {
    return (
      <EmptyState
        title="Report not found"
        description="Open an existing report from the reports list."
        action={
          <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/reports">
            Back to reports
          </Link>
        }
      />
    );
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <PageHeader
          eyebrow="Export report"
          title={report.title}
          description={`Report #${report.id} · Analysis #${report.analysis_id}`}
        />
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href={`/reports?analysis_id=${report.analysis_id}`}>
            Back to list
          </Link>
          <Link className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700" href={`/dashboard/${report.analysis_id}`}>
            Back to dashboard
          </Link>
          <button className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300" disabled={!report.content_markdown} type="button" onClick={() => void copyMarkdown()}>
            {copied ? "Copied" : "Copy Markdown"}
          </button>
          <button className="cursor-not-allowed rounded-md border border-slate-200 bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-400" disabled type="button">
            PDF pending
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Top country" value={dashboard?.country_scores[0]?.country ?? "-"} helperText="From dashboard aggregation" />
        <MetricCard label="Top score" value={formatScore(dashboard?.top_recommendations[0]?.total_score)} helperText="Backend scoring result" />
        <MetricCard label="Sources" value={dashboard?.data_sources_used.length ?? "-"} helperText="API, sample, and fallback labels" />
        <MetricCard label="PDF" value={report.pdf_url ? "Ready" : "Pending"} helperText="PDF export is disabled in v1" />
      </div>

      <div className="mt-5 grid gap-4">
        <FallbackNotice
          source="sample"
          title="Evidence boundary"
          description="The report is based on structured analysis results. Competitor samples do not represent real sales."
        />
        {fallbackUsed ? (
          <FallbackNotice
            source="csv"
            title="Fallback evidence included"
            description="Review live data before production launch decisions."
          />
        ) : null}
      </div>

      <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        {report.content_html ? (
          <div dangerouslySetInnerHTML={{ __html: report.content_html }} />
        ) : report.content_markdown ? (
          <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-700">{report.content_markdown}</pre>
        ) : (
          <EmptyState title="Report content is empty" description="Regenerate this report from the report list." />
        )}
      </section>
    </div>
  );
}

function formatScore(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(1) : String(value);
}
