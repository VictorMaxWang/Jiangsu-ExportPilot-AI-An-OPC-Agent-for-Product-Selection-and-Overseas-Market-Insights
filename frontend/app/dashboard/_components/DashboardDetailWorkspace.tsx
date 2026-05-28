"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ChartPanel,
  CompetitorPriceRangeChart,
  ContentThemeCloud,
  CountryRecommendationChart,
  ScoreRankingBarChart,
} from "../../../components/charts";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import { MetricCard } from "../../_components/MetricCard";
import { PageHeader } from "../../_components/PageHeader";
import {
  DashboardDataSourceUsed,
  DashboardPriceRange,
  DashboardRecommendation,
  DashboardResponse,
  DashboardRiskCard,
  getDashboard,
  getFriendlyErrorMessage,
} from "../../_lib/api-client";

const DEMO_SOURCE_NOTICE =
  "当前 Demo 使用公开 API、缓存、样本数据与 CSV fallback。竞品样本不代表真实销量，仅作为价格与内容信号。";

type DashboardDetailWorkspaceProps = {
  analysisId: number;
};

export function DashboardDetailWorkspace({ analysisId }: DashboardDetailWorkspaceProps) {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadDashboard() {
      setLoading(true);
      setError(null);
      try {
        const response = await getDashboard(analysisId, controller.signal);
        setDashboard(response);
      } catch (requestError) {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }
        setError(getFriendlyErrorMessage(requestError));
      } finally {
        setLoading(false);
      }
    }

    void loadDashboard();
    return () => controller.abort();
  }, [analysisId]);

  const topRecommendation = dashboard?.top_recommendations[0] ?? null;
  const topCountry = dashboard?.country_scores[0] ?? null;
  const topPriceRange = dashboard?.price_ranges[0] ?? null;
  const fallbackUsed = useMemo(() => {
    if (!dashboard) {
      return false;
    }
    return (
      dashboard.data_sources_used.some((source) => source.fallback_used) ||
      dashboard.top_recommendations.some((item) => item.fallback_used || item.ai_fallback_used)
    );
  }, [dashboard]);

  if (loading) {
    return (
      <div>
        <PageHeader
          eyebrow="市场看板 / Market Dashboard"
          title={`分析 #${analysisId} 市场机会看板`}
          description="正在读取本次智能体分析的评分、竞品价格带、内容趋势和数据来源。"
        />
        <LoadingState label="正在加载市场看板数据" rows={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader
          eyebrow="市场看板 / Market Dashboard"
          title={`分析 #${analysisId} 市场机会看板`}
          description="看板只展示已完成或已落库的分析结果，不会在页面加载时重新调用第三方 API。"
        />
        <ErrorState
          message={error}
          retryAction={
            <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
              运行分析
            </Link>
          }
        />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <EmptyState
        title="请先运行一次分析"
        description="请先在运行分析页选择企业、产品和目标国家，待工作流完成后查看市场看板。"
        action={
          <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
            运行分析
          </Link>
        }
      />
    );
  }

  return (
    <div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <PageHeader
          eyebrow="市场看板 / Market Dashboard"
          title={`分析 #${dashboard.analysis_id} 市场机会看板`}
          description="汇总产品机会评分、国家推荐、竞品价格区间、趋势主题、风险提示和数据来源，便于比赛现场讲解选品逻辑。"
        />
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white"
            href={`/reports?analysis_id=${dashboard.analysis_id}`}
          >
            查看出海报告
          </Link>
          <Link
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700"
            href={`/marketing?analysis_id=${dashboard.analysis_id}`}
          >
            生成营销文案
          </Link>
          <Link
            className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700"
            href="/analysis/run"
          >
            重新运行分析
          </Link>
        </div>
      </div>

      <div className="grid gap-4">
        <FallbackNotice source="sample" title="Demo 数据说明" description={DEMO_SOURCE_NOTICE} />
        {fallbackUsed ? (
          <FallbackNotice
            source="csv"
            title="fallback_used 不是失败"
            description="该结果包含公开 API、样本、缓存或 CSV fallback 信号，适合 Demo 展示和方向判断，正式投放前仍需复核实时平台证据。"
          />
        ) : null}
      </div>

      {dashboard.product_scores.length === 0 ? (
        <div className="mt-5">
          <EmptyState
            title="请先运行一次分析"
            description="当前分析还没有可展示的机会评分。请等待智能体工作流完成，或重新运行分析。"
            action={
              <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/analysis/run">
                运行分析
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="推荐市场"
              value={topCountry?.country ?? "-"}
              helperText="按目标国家最高机会分排序"
            />
            <MetricCard
              label="最高机会分"
              value={formatScore(topRecommendation?.total_score)}
              helperText="来自 R16 确定性评分模型"
            />
            <MetricCard
              label="竞品价格带"
              value={formatPriceRange(topPriceRange)}
              helperText="仅表示样本价格区间"
            />
            <MetricCard
              label="数据链路"
              value={dashboard.data_sources_used.length}
              helperText="公开 API、样本与 fallback 均有标记"
            />
          </div>

          <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="grid gap-5">
              <ChartPanel
                title="产品机会评分"
                description="按产品与国家组合展示 total_score。"
                sourceNote="数据源：后端 OpportunityScore 聚合公开 API、CSV fallback、内容趋势与贸易样本后生成。"
                isEmpty={dashboard.product_scores.length === 0}
              >
                <ScoreRankingBarChart items={dashboard.product_scores} />
              </ChartPanel>

              <ChartPanel
                title="国家推荐评分"
                description="按国家聚合平均分和最高分。"
                sourceNote="数据源：本次 analysis_id 下的评分结果按国家聚合，仅用于演示市场优先级。"
                isEmpty={dashboard.country_scores.length === 0}
              >
                <CountryRecommendationChart items={dashboard.country_scores} />
              </ChartPanel>

              <ChartPanel
                title="竞品价格区间"
                description="展示公开 API 或样本竞品的最低价、中位价和最高价。"
                sourceNote="数据源：Etsy/平台样本与 competitor_samples.csv；竞品样本不代表真实销量，仅作为价格与内容信号。"
                isEmpty={dashboard.price_ranges.length === 0}
              >
                <CompetitorPriceRangeChart items={dashboard.price_ranges} />
                <PriceNoticeList items={dashboard.price_ranges} />
              </ChartPanel>

              <ChartPanel
                title="内容趋势标签云"
                description="来自 R17 content_trends 工作流状态；没有趋势主题时不编造标签。"
                sourceNote="数据源：YouTube、讨论样本、内容趋势 CSV fallback 与 AI/规则解析结果。"
                isEmpty={dashboard.content_themes.length === 0}
                emptyTitle="暂无趋势主题"
                emptyDescription="当前分析没有可展示的 content_themes。"
              >
                <ContentThemeCloud items={dashboard.content_themes} />
              </ChartPanel>
            </div>

            <div className="grid content-start gap-5">
              <RecommendationsPanel items={dashboard.top_recommendations} />
              <RiskPanel items={dashboard.risk_cards} />
              <SourcesPanel items={dashboard.data_sources_used} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function RecommendationsPanel({ items }: { items: DashboardRecommendation[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-semibold text-ink">推荐产品卡片</h2>
      <div className="mt-4 grid gap-3">
        {items.length === 0 ? (
          <EmptyState title="暂无推荐结果" description="当前分析没有可展示的 top_recommendations。" />
        ) : (
          items.map((item) => (
            <article key={`${item.product_id}-${item.country}`} className="border-t border-slate-100 pt-4 first:border-t-0 first:pt-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">
                    #{item.rank ?? "-"} {item.product_name}
                  </p>
                  <p className="mt-1 text-xs font-semibold text-river">{item.country} · {formatScore(item.total_score)} 分</p>
                </div>
                {item.fallback_used || item.ai_fallback_used ? (
                  <span className="rounded-md bg-wheat/15 px-2 py-1 text-xs font-semibold text-ink">fallback</span>
                ) : null}
              </div>
              {item.reason ? <p className="mt-3 text-sm leading-6 text-slate-600">{item.reason}</p> : null}
              {item.next_action ? (
                <p className="mt-3 rounded-lg bg-jade/10 px-3 py-2 text-sm font-medium leading-6 text-jade">
                  {item.next_action}
                </p>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function RiskPanel({ items }: { items: DashboardRiskCard[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-semibold text-ink">风险提示卡片</h2>
      <div className="mt-4 grid gap-3">
        {items.length === 0 ? (
          <EmptyState title="暂无风险提示" description="当前评分结果没有生成独立风险卡片。" />
        ) : (
          items.map((item, index) => (
            <article key={`${item.title}-${item.product_id ?? "all"}-${item.country ?? "all"}-${index}`} className="border-t border-slate-100 pt-4 first:border-t-0 first:pt-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-md px-2 py-1 text-xs font-semibold ${riskClassName(item.severity)}`}>
                  {item.severity}
                </span>
                <h3 className="text-sm font-semibold text-ink">{item.title}</h3>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-600">{item.message}</p>
              <p className="mt-2 text-xs text-slate-500">
                {item.product_name ?? "全部产品"} · {item.country ?? "全部国家"} · {item.source}
              </p>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function SourcesPanel({ items }: { items: DashboardDataSourceUsed[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-semibold text-ink">数据源使用说明</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">{DEMO_SOURCE_NOTICE}</p>
      <div className="mt-4 grid gap-3">
        {items.length === 0 ? (
          <EmptyState title="暂无来源记录" description="当前分析没有可展示的数据源记录。" />
        ) : (
          items.map((item) => (
            <div key={`${item.provider}-${item.label}-${item.source_type}`} className="border-t border-slate-100 pt-3 first:border-t-0 first:pt-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">{item.provider}</p>
                <span className={`rounded-md px-2 py-1 text-xs font-semibold ${item.fallback_used ? "bg-wheat/15 text-ink" : "bg-jade/10 text-jade"}`}>
                  {item.fallback_used ? "fallback" : item.api_invoked ? "api" : item.source_type}
                </span>
              </div>
              <p className="mt-1 text-sm leading-6 text-slate-600">{item.label}</p>
              {item.detail ? <p className="mt-1 text-xs leading-5 text-slate-500">{item.detail}</p> : null}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function PriceNoticeList({ items }: { items: DashboardPriceRange[] }) {
  const notices = items
    .map((item) => item.sample_notice || item.price_suggestion)
    .filter((notice): notice is string => Boolean(notice))
    .slice(0, 3);
  if (notices.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 grid gap-2">
      {notices.map((notice, index) => (
        <p key={`${notice}-${index}`} className="rounded-md bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
          {notice}
        </p>
      ))}
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

function formatPriceRange(value: DashboardPriceRange | null): string {
  if (!value) {
    return "-";
  }
  const min = toNumber(value.min_price);
  const max = toNumber(value.max_price);
  if (min <= 0 && max <= 0) {
    return "-";
  }
  const prefix = value.currency ? `${value.currency} ` : "";
  return `${prefix}${min.toFixed(0)}-${max.toFixed(0)}`;
}

function toNumber(value: string | number | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function riskClassName(severity: DashboardRiskCard["severity"]): string {
  const classNames: Record<DashboardRiskCard["severity"], string> = {
    low: "bg-jade/10 text-jade",
    medium: "bg-wheat/15 text-ink",
    high: "bg-red-50 text-red-700",
  };
  return classNames[severity];
}
