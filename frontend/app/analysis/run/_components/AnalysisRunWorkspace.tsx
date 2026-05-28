"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentFlowTimeline, AGENT_STEP_LABELS } from "../../../../components/agent-flow";
import { EmptyState } from "../../../_components/EmptyState";
import { ErrorState } from "../../../_components/ErrorState";
import { FallbackNotice } from "../../../_components/FallbackNotice";
import { LoadingState } from "../../../_components/LoadingState";
import {
  AnalysisStatusResponse,
  AnalysisStepLog,
  AnalysisWorkflowStatus,
  Company,
  Product,
  getAnalysisStatus,
  getFriendlyErrorMessage,
  listCompanies,
  listProducts,
  startAnalysisRun,
} from "../../../_lib/api-client";

type CompletionTarget = "report" | "dashboard";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_COUNT = 80;

const STEP_IDS = Object.keys(AGENT_STEP_LABELS);

export function AnalysisRunWorkspace() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [countryInput, setCountryInput] = useState("US, JP");
  const [competitorLimit, setCompetitorLimit] = useState(20);
  const [completionTarget, setCompletionTarget] = useState<CompletionTarget>("report");
  const [loading, setLoading] = useState(true);
  const [productsLoading, setProductsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatusResponse | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const runTokenRef = useRef(0);
  const pollCountRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const redirectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearPollingTimer = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const clearPolling = useCallback(() => {
    clearPollingTimer();
    abortRef.current?.abort();
    abortRef.current = null;
  }, [clearPollingTimer]);

  const clearRedirect = useCallback(() => {
    if (redirectRef.current) {
      clearTimeout(redirectRef.current);
      redirectRef.current = null;
    }
  }, []);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.id === selectedCompanyId) ?? null,
    [companies, selectedCompanyId],
  );

  const selectedProduct = useMemo(
    () => products.find((product) => product.id === selectedProductId) ?? null,
    [products, selectedProductId],
  );

  const terminal = analysisStatus ? isTerminalStatus(analysisStatus.status) : false;
  const fallbackUsed = analysisStatus?.status === "fallback_used" || Boolean(analysisStatus?.fallback_used_providers.length);
  const timelineSteps = analysisStatus?.step_logs.length ? analysisStatus.step_logs : buildInitialSteps();

  const loadProducts = useCallback(async (companyId: number, selectFirst = false) => {
    setProductsLoading(true);
    setError(null);
    try {
      const productResponse = await listProducts(companyId);
      setProducts(productResponse.items);
      setSelectedProductId((current) => {
        if (!selectFirst && current && productResponse.items.some((product) => product.id === current)) {
          return current;
        }
        return productResponse.items[0]?.id ?? null;
      });
    } catch (requestError) {
      setProducts([]);
      setSelectedProductId(null);
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setProductsLoading(false);
    }
  }, []);

  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const companyResponse = await listCompanies();
      setCompanies(companyResponse.items);
      const firstCompany = companyResponse.items[0] ?? null;
      setSelectedCompanyId(firstCompany?.id ?? null);
      setCountryInput(firstCompany?.target_countries?.join(", ") || "US, JP");
      if (firstCompany) {
        await loadProducts(firstCompany.id, true);
      } else {
        setProducts([]);
        setSelectedProductId(null);
      }
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [loadProducts]);

  useEffect(() => {
    void loadInitialData();
    return () => {
      clearPolling();
      clearRedirect();
    };
  }, [clearPolling, clearRedirect, loadInitialData]);

  function handleCompanyChange(value: string) {
    const companyId = value ? Number(value) : null;
    setSelectedCompanyId(companyId);
    setSelectedProductId(null);
    setAnalysisStatus(null);
    setAnalysisId(null);
    const company = companies.find((item) => item.id === companyId) ?? null;
    setCountryInput(company?.target_countries?.join(", ") || countryInput);
    if (companyId) {
      void loadProducts(companyId, true);
    } else {
      setProducts([]);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (!selectedCompanyId) {
      setError("请先选择企业。");
      return;
    }
    if (!selectedProductId) {
      setError("请先选择产品。");
      return;
    }

    const invalidCountries = getInvalidCountryTokens(countryInput);
    if (invalidCountries.length > 0) {
      setError(`目标国家仅支持 2 或 3 位国家码：${invalidCountries.join(", ")}`);
      return;
    }

    const countries = parseCountries(countryInput);
    if (countries.length === 0) {
      setError("目标国家需填写 2 或 3 位国家码，例如 US、JP、GB。");
      return;
    }

    clearPolling();
    clearRedirect();
    const token = runTokenRef.current + 1;
    runTokenRef.current = token;
    pollCountRef.current = 0;
    setSubmitting(true);
    setAnalysisStatus(null);
    setAnalysisId(null);
    setNotice("分析任务已提交，正在等待智能体工作流接收。");

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const started = await startAnalysisRun(
        {
          company_id: selectedCompanyId,
          product_ids: [selectedProductId],
          target_countries: countries,
          competitor_limit: competitorLimit,
        },
        controller.signal,
      );
      if (token !== runTokenRef.current) {
        return;
      }
      setAnalysisId(started.analysis_id);
      setNotice(`分析 #${started.analysis_id} 已启动，当前轮询 ${started.status_url}。`);
      void pollStatus(started.analysis_id, token);
    } catch (requestError) {
      if (isAbortError(requestError)) {
        return;
      }
      setSubmitting(false);
      setError(getFriendlyErrorMessage(requestError));
    }
  }

  async function pollStatus(runId: number, token: number) {
    clearPollingTimer();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const status = await getAnalysisStatus(runId, controller.signal);
      if (token !== runTokenRef.current) {
        return;
      }

      setAnalysisStatus(status);
      if (isTerminalStatus(status.status) || status.finished_at) {
        setSubmitting(false);
        setNotice(buildTerminalNotice(status, completionTarget));
        if (status.status !== "failed") {
          scheduleRedirect(status, completionTarget);
        }
        return;
      }

      pollCountRef.current += 1;
      if (pollCountRef.current >= MAX_POLL_COUNT) {
        setSubmitting(false);
        setNotice("轮询已达到演示保护上限，后台任务可能仍在运行，可稍后刷新状态。");
        return;
      }

      timeoutRef.current = setTimeout(() => {
        void pollStatus(runId, token);
      }, POLL_INTERVAL_MS);
    } catch (requestError) {
      if (isAbortError(requestError) || token !== runTokenRef.current) {
        return;
      }
      setSubmitting(false);
      setError(getFriendlyErrorMessage(requestError));
    }
  }

  function scheduleRedirect(status: AnalysisStatusResponse, target: CompletionTarget) {
    clearRedirect();
    const href =
      target === "report"
        ? status.next_page_url || `/reports?analysis_id=${status.analysis_id}`
        : `/dashboard/${status.analysis_id}`;
    redirectRef.current = setTimeout(() => {
      router.push(href);
    }, 1800);
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
      <section className="grid gap-5">
        <Panel title="分析参数">
          {loading ? (
            <LoadingState label="正在加载企业与产品" rows={4} />
          ) : companies.length === 0 ? (
            <EmptyState
              title="暂无企业"
              description="请先录入企业，再启动智能体协作分析。"
            />
          ) : (
            <form className="grid gap-4" onSubmit={handleSubmit}>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">选择企业</span>
                <select
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                  required
                  value={selectedCompanyId ?? ""}
                  onChange={(event) => handleCompanyChange(event.target.value)}
                >
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">选择产品</span>
                <select
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:bg-slate-100"
                  disabled={productsLoading || products.length === 0}
                  required
                  value={selectedProductId ?? ""}
                  onChange={(event) => setSelectedProductId(event.target.value ? Number(event.target.value) : null)}
                >
                  {productsLoading ? <option value="">产品加载中</option> : null}
                  {!productsLoading && products.length === 0 ? <option value="">该企业暂无产品</option> : null}
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.product_name_cn}
                      {product.product_name_en ? ` / ${product.product_name_en}` : ""}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">选择目标国家</span>
                <input
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                  placeholder="US, JP, GB"
                  value={countryInput}
                  onChange={(event) => setCountryInput(event.target.value)}
                />
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">竞品采集上限</span>
                  <input
                    className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                    max={50}
                    min={1}
                    type="number"
                    value={competitorLimit}
                    onChange={(event) => setCompetitorLimit(Number(event.target.value))}
                  />
                </label>
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">完成后跳转</span>
                  <select
                    className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                    value={completionTarget}
                    onChange={(event) => setCompletionTarget(event.target.value as CompletionTarget)}
                  >
                    <option value="report">报告页</option>
                    <option value="dashboard">看板页</option>
                  </select>
                </label>
              </div>

              <button
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={submitting || productsLoading || !selectedCompanyId || !selectedProductId}
                type="submit"
              >
                {submitting ? "智能体分析中" : "开始智能体分析"}
              </button>
            </form>
          )}
        </Panel>

        <Panel title="当前任务">
          <div className="grid gap-3">
            <DetailItem label="分析 ID" value={analysisId ? `#${analysisId}` : "-"} />
            <DetailItem label="企业" value={selectedCompany?.name ?? "-"} />
            <DetailItem
              label="产品"
              value={
                selectedProduct
                  ? `${selectedProduct.product_name_cn}${selectedProduct.product_name_en ? ` / ${selectedProduct.product_name_en}` : ""}`
                  : "-"
              }
            />
            <DetailItem label="目标国家" value={parseCountries(countryInput).join(", ") || "-"} />
            <DetailItem label="整体状态" value={analysisStatus?.status ?? "waiting"} />
          </div>
          {notice ? (
            <p className="mt-4 rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium leading-6 text-jade">
              {notice}
            </p>
          ) : null}
          {error ? (
            <div className="mt-4">
              <ErrorState message={error} />
            </div>
          ) : null}
          {!selectedProductId && selectedCompanyId && !productsLoading ? (
            <p className="mt-4 text-sm leading-6 text-slate-500">
              当前企业没有可选产品，可前往 <Link className="font-semibold text-river" href="/products">产品页</Link> 创建或导入样本。
            </p>
          ) : null}
        </Panel>

        {analysisStatus ? (
          <Panel title="结果摘要">
            <div className="grid gap-3 sm:grid-cols-2">
              <DetailItem label="评分条目" value={String(analysisStatus.scoring_summary.item_count)} />
              <DetailItem label="最高分" value={formatScore(analysisStatus.scoring_summary.top_score)} />
              <DetailItem label="推荐国家" value={analysisStatus.scoring_summary.top_country ?? "-"} />
              <DetailItem label="数据源" value={analysisStatus.used_providers.join(", ") || "csv_fallback"} />
            </div>
            {terminal && analysisStatus.status !== "failed" ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white"
                  href={analysisStatus.next_page_url || `/reports?analysis_id=${analysisStatus.analysis_id}`}
                >
                  查看报告
                </Link>
                <Link
                  className="rounded-md border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700"
                  href={`/dashboard/${analysisStatus.analysis_id}`}
                >
                  查看看板
                </Link>
              </div>
            ) : null}
          </Panel>
        ) : null}
      </section>

      <section className="grid gap-5">
        <Panel title="智能体协作分析">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-ink">9 个后端智能体按顺序执行</p>
              <p className="mt-1 text-xs text-slate-500">每 {POLL_INTERVAL_MS / 1000} 秒读取一次状态，完成后停止轮询。</p>
            </div>
            <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${overallStatusClassName(analysisStatus?.status ?? "waiting")}`}>
              {analysisStatus?.status ?? "waiting"}
            </span>
          </div>
          <AgentFlowTimeline currentStepId={analysisStatus?.current_step} steps={timelineSteps} />
        </Panel>

        {fallbackUsed ? (
          <FallbackNotice
            source="sample"
            title="fallback_used 不是失败"
            description="该步骤使用本地样本数据保障演示稳定。完成态 fallback_used 表示流程已产出结果，但部分公开 API 或 AI 输出走了兜底路径。"
          />
        ) : null}

        {analysisStatus?.status === "failed" ? (
          <ErrorState message={analysisStatus.error_message || "智能体工作流失败，请检查失败步骤。"} />
        ) : null}
      </section>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-4 text-sm leading-6 text-slate-600">{children}</div>
    </section>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 truncate font-medium text-ink">{value}</p>
    </div>
  );
}

function buildInitialSteps(): AnalysisStepLog[] {
  return STEP_IDS.map((stepId) => ({
    step_id: stepId,
    node: stepIdToNode(stepId),
    title: AGENT_STEP_LABELS[stepId],
    status: "waiting",
    started_at: null,
    finished_at: null,
    duration_ms: null,
    input_summary: {},
    output_summary: {},
    sources: [],
    fallback_used: false,
    fallback_reason: null,
    error_code: null,
    error_message: null,
  }));
}

function stepIdToNode(stepId: string): string {
  const nodes: Record<string, string> = {
    "01_company_profiling": "CompanyProfilingAgent",
    "02_product_understanding": "ProductUnderstandingAgent",
    "03_data_collection": "DataCollectionAgent",
    "04_competitor_analysis": "CompetitorAnalysisAgent",
    "05_market_profiling": "MarketProfilingAgent",
    "06_content_trend": "ContentTrendAgent",
    "07_opportunity_scoring": "OpportunityScoringAgent",
    "08_marketing_prep": "MarketingPrepAgent",
    "09_report_prep": "ReportPrepAgent",
  };
  return nodes[stepId] ?? "WorkflowAgent";
}

function parseCountries(value: string): string[] {
  const seen = new Set<string>();
  return countryTokens(value)
    .map((country) => country.trim().toUpperCase())
    .filter((country) => /^[A-Z]{2,3}$/.test(country))
    .filter((country) => {
      if (seen.has(country)) {
        return false;
      }
      seen.add(country);
      return true;
    });
}

function getInvalidCountryTokens(value: string): string[] {
  return countryTokens(value).filter((country) => !/^[A-Z]{2,3}$/.test(country.toUpperCase()));
}

function countryTokens(value: string): string[] {
  return value
    .split(/[,，\s]+/)
    .map((country) => country.trim())
    .filter(Boolean);
}

function isTerminalStatus(status: AnalysisWorkflowStatus): boolean {
  return status === "success" || status === "failed" || status === "fallback_used";
}

function buildTerminalNotice(status: AnalysisStatusResponse, target: CompletionTarget): string {
  if (status.status === "failed") {
    return "分析已停止，失败步骤已在右侧标出。";
  }
  const targetLabel = target === "report" ? "报告页" : "看板页";
  return `分析 #${status.analysis_id} 已完成，正在跳转${targetLabel}。`;
}

function formatScore(value: string | number | null): string {
  if (value === null) {
    return "-";
  }
  return String(value);
}

function overallStatusClassName(status: AnalysisWorkflowStatus): string {
  const classNames: Record<AnalysisWorkflowStatus, string> = {
    waiting: "bg-slate-100 text-slate-600 ring-slate-200",
    running: "bg-river/10 text-river ring-river/20",
    success: "bg-jade/10 text-jade ring-jade/20",
    failed: "bg-red-50 text-red-700 ring-red-200",
    fallback_used: "bg-wheat/15 text-ink ring-wheat/30",
  };
  return classNames[status];
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
