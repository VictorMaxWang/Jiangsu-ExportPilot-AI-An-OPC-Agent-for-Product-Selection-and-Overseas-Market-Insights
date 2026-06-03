"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentFlowTimeline, AGENT_NODE_LABELS, AGENT_STEP_LABELS } from "../../../../components/agent-flow";
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
  ProductDraft,
  generateReport,
  getAnalysisStatus,
  getFriendlyErrorMessage,
  listProductIntakeDrafts,
  listCompanies,
  listProducts,
  startAnalysisRun,
} from "../../../_lib/api-client";

const POLL_INTERVAL_MS = 1500;
const MAX_POLL_COUNT = 80;
const DEMO_COUNTRY_INPUT = "US, JP, GB";
const DEMO_PRODUCT_COUNT = 3;
const DEFAULT_COMPETITOR_LIMIT = 20;

const STEP_IDS = Object.keys(AGENT_STEP_LABELS);

type EvidenceCard = {
  key: string;
  title: string;
  status: string;
  detail: string;
  tone: "api" | "csv" | "ai";
};

export function AnalysisRunWorkspace() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [recentIntakeDrafts, setRecentIntakeDrafts] = useState<ProductDraft[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [countryInput, setCountryInput] = useState(DEMO_COUNTRY_INPUT);
  const [competitorLimit, setCompetitorLimit] = useState(DEFAULT_COMPETITOR_LIMIT);
  const [loading, setLoading] = useState(true);
  const [productsLoading, setProductsLoading] = useState(false);
  const [intakeDraftsLoading, setIntakeDraftsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatusResponse | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const runTokenRef = useRef(0);
  const pollCountRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

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

  const resetRunState = useCallback(() => {
    clearPolling();
    runTokenRef.current += 1;
    pollCountRef.current = 0;
    setSubmitting(false);
    setGeneratingReport(false);
    setAnalysisStatus(null);
    setAnalysisId(null);
    setError(null);
    setNotice(null);
  }, [clearPolling]);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.id === selectedCompanyId) ?? null,
    [companies, selectedCompanyId],
  );

  const selectedProducts = useMemo(
    () => products.filter((product) => selectedProductIds.includes(product.id)),
    [products, selectedProductIds],
  );

  const selectedLowConfidenceImportDraft = useMemo(
    () =>
      recentIntakeDrafts.find(
        (draft) =>
          draft.low_confidence &&
          draft.confirmed_product_id !== null &&
          selectedProductIds.includes(draft.confirmed_product_id),
      ) ?? null,
    [recentIntakeDrafts, selectedProductIds],
  );

  const terminal = analysisStatus ? isTerminalStatus(analysisStatus.status) : false;
  const fallbackUsed = analysisStatus?.status === "fallback_used" || Boolean(analysisStatus?.fallback_used_providers.length);
  const timelineSteps = analysisStatus?.step_logs.length ? analysisStatus.step_logs : buildInitialSteps();

  const loadProducts = useCallback(async (companyId: number, selectDemoDefaults = false): Promise<Product[]> => {
    setProductsLoading(true);
    setError(null);
    try {
      const productResponse = await listProducts(companyId);
      const items = productResponse.items;
      setProducts(items);
      setSelectedProductIds((current) => {
        if (!selectDemoDefaults) {
          const retained = current.filter((productId) => items.some((product) => product.id === productId));
          if (retained.length > 0) {
            return retained;
          }
        }
        return firstProductIds(items);
      });
      return items;
    } catch (requestError) {
      setProducts([]);
      setSelectedProductIds([]);
      setError(getFriendlyErrorMessage(requestError));
      return [];
    } finally {
      setProductsLoading(false);
    }
  }, []);

  const loadRecentIntakeDrafts = useCallback(async (companyId: number): Promise<ProductDraft[]> => {
    setIntakeDraftsLoading(true);
    try {
      const draftResponse = await listProductIntakeDrafts({
        company_id: companyId,
        status: "confirmed",
        limit: 5,
        offset: 0,
      });
      const confirmedDrafts = draftResponse.items.filter((draft) => draft.confirmed_product_id !== null);
      setRecentIntakeDrafts(confirmedDrafts);
      return confirmedDrafts;
    } catch {
      setRecentIntakeDrafts([]);
      return [];
    } finally {
      setIntakeDraftsLoading(false);
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
      setCountryInput(DEMO_COUNTRY_INPUT);
      setCompetitorLimit(DEFAULT_COMPETITOR_LIMIT);
      if (firstCompany) {
        await Promise.all([loadProducts(firstCompany.id, true), loadRecentIntakeDrafts(firstCompany.id)]);
      } else {
        setProducts([]);
        setSelectedProductIds([]);
        setRecentIntakeDrafts([]);
      }
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [loadProducts, loadRecentIntakeDrafts]);

  useEffect(() => {
    void loadInitialData();
    return () => {
      clearPolling();
    };
  }, [clearPolling, loadInitialData]);

  function handleCompanyChange(value: string) {
    const companyId = value ? Number(value) : null;
    resetRunState();
    setSelectedCompanyId(companyId);
    setSelectedProductIds([]);
    setCountryInput(DEMO_COUNTRY_INPUT);
    if (companyId) {
      void loadProducts(companyId, true);
      void loadRecentIntakeDrafts(companyId);
    } else {
      setProducts([]);
      setRecentIntakeDrafts([]);
    }
  }

  async function applyRecommendedDemoConfig() {
    const demoCompany = companies[0] ?? null;
    if (!demoCompany) {
      setError("请先创建企业，再使用推荐演示配置。");
      return;
    }
    resetRunState();
    setSelectedCompanyId(demoCompany.id);
    setCountryInput(DEMO_COUNTRY_INPUT);
    setCompetitorLimit(DEFAULT_COMPETITOR_LIMIT);
    await Promise.all([loadProducts(demoCompany.id, true), loadRecentIntakeDrafts(demoCompany.id)]);
    setNotice("已应用推荐演示配置：首个企业、前 3 个产品、US/JP/GB 和 20 条竞品采集上限。");
  }

  function toggleProduct(productId: number, checked: boolean) {
    resetRunState();
    setSelectedProductIds((current) => {
      if (!checked) {
        return current.filter((id) => id !== productId);
      }
      if (current.includes(productId)) {
        return current;
      }
      return [...current, productId];
    });
  }

  function selectRecentIntakeProduct(draft: ProductDraft) {
    if (draft.confirmed_product_id === null) {
      return;
    }
    resetRunState();
    setSelectedProductIds([draft.confirmed_product_id]);
    if (draft.low_confidence) {
      setNotice("该产品来自 AI 识别结果，建议确认字段后再分析。");
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

    const productIds = selectedProductIds.filter((productId) => products.some((product) => product.id === productId));
    if (productIds.length === 0) {
      setError("请至少选择一个产品。");
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
          product_ids: productIds,
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
        setNotice(buildTerminalNotice(status));
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

  async function handleGenerateReport() {
    const reportAnalysisId = analysisStatus?.analysis_id ?? analysisId;
    if (!reportAnalysisId) {
      setError("请先完成一次分析，再生成报告。");
      return;
    }
    setGeneratingReport(true);
    setError(null);
    setNotice(null);
    try {
      const report = await generateReport({ analysis_id: reportAnalysisId, force_regenerate: false });
      router.push(`/reports/${report.id}`);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setGeneratingReport(false);
    }
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
              action={
                <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/companies">
                  去创建企业
                </Link>
              }
            />
          ) : (
            <form className="grid gap-4" onSubmit={handleSubmit}>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-river/20 bg-river/5 p-4">
                <div>
                  <p className="text-sm font-semibold text-ink">推荐演示配置</p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">首个企业、前 3 个产品、US/JP/GB，适合 5 分钟现场演示。</p>
                </div>
                <button
                  className="rounded-md border border-river/30 bg-white px-3 py-2 text-sm font-semibold text-river disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={productsLoading || submitting}
                  type="button"
                  onClick={() => void applyRecommendedDemoConfig()}
                >
                  使用推荐演示配置
                </button>
              </div>

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

              <div className="grid gap-2 rounded-lg border border-river/20 bg-river/5 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-ink">选择最近智能导入产品</p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">可直接选择已确认入库的截图/链接导入产品进入分析流程。</p>
                  </div>
                  <Link
                    className="rounded-md border border-river/30 bg-white px-3 py-2 text-sm font-semibold text-river"
                    href={selectedCompanyId ? `/products/import?company_id=${selectedCompanyId}` : "/products/import"}
                  >
                    导入新商品
                  </Link>
                </div>
                {intakeDraftsLoading ? (
                  <LoadingState label="正在加载智能导入产品" rows={2} />
                ) : recentIntakeDrafts.length === 0 ? (
                  <p className="text-sm text-slate-500">当前企业暂无已确认的智能导入产品。</p>
                ) : (
                  <div className="grid gap-2">
                    {recentIntakeDrafts.map((draft) => (
                      <button
                        key={draft.id}
                        className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                          draft.confirmed_product_id !== null && selectedProductIds.includes(draft.confirmed_product_id)
                            ? "border-river/40 bg-white text-ink shadow-sm"
                            : "border-slate-200 bg-white/70 text-slate-700 hover:border-river/30 hover:bg-white"
                        }`}
                        disabled={draft.confirmed_product_id === null || productsLoading || submitting}
                        type="button"
                        onClick={() => selectRecentIntakeProduct(draft)}
                      >
                        <span className="block font-semibold text-ink">
                          {draft.product_name_cn || draft.product_name_en || `草稿 #${draft.id}`}
                        </span>
                        <span className="mt-1 block text-xs text-slate-500">
                          来源 {draft.source_platform || "未知"} · 置信度 {draft.confidence_score ?? "未记录"}
                          {draft.low_confidence ? " · 低置信度" : ""}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                {selectedLowConfidenceImportDraft ? (
                  <p className="rounded-lg border border-wheat/40 bg-wheat/10 p-3 text-sm font-medium leading-6 text-ink">
                    该产品来自 AI 识别结果，建议确认字段后再分析。
                  </p>
                ) : null}
              </div>

              <div className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">选择产品</span>
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  {productsLoading ? (
                    <LoadingState label="产品加载中" rows={2} />
                  ) : products.length === 0 ? (
                    <EmptyState
                      title="该企业暂无产品"
                      description="请先前往产品页导入南通家纺样本产品。"
                      action={
                        <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/products">
                          去导入产品
                        </Link>
                      }
                    />
                  ) : (
                    <div className="grid gap-2">
                      {products.map((product) => (
                        <label
                          key={product.id}
                          className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                        >
                          <input
                            checked={selectedProductIds.includes(product.id)}
                            className="mt-1 h-4 w-4 rounded border-slate-300 text-river focus:ring-river"
                            type="checkbox"
                            onChange={(event) => toggleProduct(product.id, event.target.checked)}
                          />
                          <span>
                            <span className="font-medium text-ink">{product.product_name_cn}</span>
                            {product.product_name_en ? <span className="text-slate-500"> / {product.product_name_en}</span> : null}
                          </span>
                        </label>
                      ))}
                      <p className="text-xs text-slate-500">默认选择前 3 个产品；可按现场讲解需要增减。</p>
                    </div>
                  )}
                </div>
              </div>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">选择目标国家</span>
                <input
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                  placeholder={DEMO_COUNTRY_INPUT}
                  value={countryInput}
                  onChange={(event) => {
                    resetRunState();
                    setCountryInput(event.target.value);
                  }}
                />
              </label>

              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">竞品采集上限</span>
                <input
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                  max={50}
                  min={1}
                  type="number"
                  value={competitorLimit}
                  onChange={(event) => {
                    resetRunState();
                    setCompetitorLimit(Number(event.target.value));
                  }}
                />
              </label>

              <button
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={submitting || productsLoading || !selectedCompanyId || selectedProductIds.length === 0}
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
            <DetailItem label="产品" value={selectedProductsLabel(selectedProducts)} />
            <DetailItem label="目标国家" value={parseCountries(countryInput).join(", ") || "-"} />
            <DetailItem label="整体状态" value={workflowStatusLabel(analysisStatus?.status ?? "waiting")} />
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
          {selectedProductIds.length === 0 && selectedCompanyId && !productsLoading ? (
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
              <DetailItem label="数据源" value={analysisStatus.used_providers.join(", ") || "CSV 兜底"} />
            </div>
            {terminal && analysisStatus.status !== "failed" ? (
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white"
                  href={`/dashboard/${analysisStatus.analysis_id}`}
                >
                  查看看板
                </Link>
                <button
                  className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={generatingReport}
                  type="button"
                  onClick={() => void handleGenerateReport()}
                >
                  {generatingReport ? "生成中" : "生成报告"}
                </button>
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
              <p className="mt-1 text-xs text-slate-500">每 {POLL_INTERVAL_MS / 1000} 秒读取一次状态，完成后停留在本页供评委选择下一步。</p>
            </div>
            <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${overallStatusClassName(analysisStatus?.status ?? "waiting")}`}>
              {workflowStatusLabel(analysisStatus?.status ?? "waiting")}
            </span>
          </div>
          <AgentFlowTimeline currentStepId={analysisStatus?.current_step} steps={timelineSteps} />
        </Panel>

        <FallbackSummary status={analysisStatus} />

        {fallbackUsed ? (
          <FallbackNotice
            source="sample"
            title="使用兜底不是失败"
            description="该步骤使用公开 API 缓存、CSV 样本或确定性 AI 模板保障演示稳定。完成态使用兜底表示流程已产出结果，需要在正式投放前复核实时证据。"
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

function FallbackSummary({ status }: { status: AnalysisStatusResponse | null }) {
  const cards = buildEvidenceCards(status);
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
      <h2 className="text-lg font-semibold text-ink">数据与兜底路径</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {cards.map((card) => (
          <article key={card.key} className={`rounded-lg border p-4 ${evidenceCardClassName(card.tone)}`}>
            <p className="text-sm font-semibold text-ink">{card.title}</p>
            <p className="mt-2 text-xs font-semibold uppercase tracking-normal text-slate-500">{card.status}</p>
            <p className="mt-2 text-sm leading-6 text-slate-700">{card.detail}</p>
          </article>
        ))}
      </div>
    </section>
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
    provider_call_count: 0,
    qwen_call_count: 0,
    timeout_count: 0,
    cache_hit_count: 0,
    fallback_count: 0,
    error_code: null,
    error_message: null,
  }));
}

function stepIdToNode(stepId: string): string {
  return AGENT_NODE_LABELS[stepId] ?? "工作流智能体";
}

function buildEvidenceCards(status: AnalysisStatusResponse | null): EvidenceCard[] {
  const apiLabels = new Set<string>();
  const csvLabels = new Set<string>();
  const aiLabels = new Set<string>();

  for (const provider of status?.provider_breakdown ?? []) {
    const label = provider.labels[0] || provider.provider;
    if (provider.api_invoked) {
      apiLabels.add(label);
    }
    if (provider.fallback_used || provider.source_types.some((type) => type.includes("csv_fallback"))) {
      csvLabels.add(label);
    }
  }

  for (const step of status?.step_logs ?? []) {
    for (const source of step.sources) {
      const provider = readSourceString(source, "provider");
      const label = readSourceString(source, "source_label") || readSourceString(source, "label") || provider || step.title;
      const sourceType = readSourceString(source, "source_type");
      const apiInvoked = readSourceBoolean(source, "api_invoked");
      const fallback = readSourceBoolean(source, "fallback_used");
      if (apiInvoked || sourceType === "api" || sourceType === "public_api") {
        apiLabels.add(label);
      }
      if (sourceType.includes("csv_fallback") || (fallback && provider !== "bailian" && sourceType !== "ai_fallback")) {
        csvLabels.add(label);
      }
      if (sourceType === "ai_fallback" || (provider === "bailian" && fallback)) {
        aiLabels.add(label);
      }
    }
    if (step.fallback_reason?.toLowerCase().includes("ai")) {
      aiLabels.add(step.title);
    }
  }

  for (const provider of status?.fallback_used_providers ?? []) {
    if (provider.toLowerCase().includes("bailian") || provider.toLowerCase().includes("ai")) {
      aiLabels.add(provider);
    } else {
      csvLabels.add(provider);
    }
  }

  return [
    {
      key: "api",
      title: "API 数据",
      status: apiLabels.size > 0 ? "已读取或尝试调用" : "等待工作流读取",
      detail: apiLabels.size > 0 ? summarizeLabels(apiLabels) : "World Bank、GDELT、Etsy、YouTube、UN Comtrade 等公开数据会在工作流中统一记录来源。",
      tone: "api",
    },
    {
      key: "csv",
      title: "CSV 兜底",
      status: csvLabels.size > 0 ? "已启用兜底" : "可用兜底",
      detail: csvLabels.size > 0 ? summarizeLabels(csvLabels) : "现场网络或平台 API 不稳定时，内置 seed CSV 会保障评分、看板和报告继续产出。",
      tone: "csv",
    },
    {
      key: "ai",
      title: "AI 兜底",
      status: aiLabels.size > 0 ? "已使用模板兜底" : "模型优先，模板兜底",
      detail: aiLabels.size > 0 ? summarizeLabels(aiLabels) : "qwen3.6-plus 不可用时，后端使用确定性模板生成解释、营销草稿或报告结构。",
      tone: "ai",
    },
  ];
}

function firstProductIds(items: Product[]): number[] {
  return items.slice(0, DEMO_PRODUCT_COUNT).map((product) => product.id);
}

function selectedProductsLabel(products: Product[]): string {
  if (products.length === 0) {
    return "-";
  }
  return products
    .map((product) => product.product_name_en ? `${product.product_name_cn} / ${product.product_name_en}` : product.product_name_cn)
    .join("、");
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

function buildTerminalNotice(status: AnalysisStatusResponse): string {
  if (status.status === "failed") {
    return "分析已停止，失败步骤已在右侧标出。";
  }
  return `分析 #${status.analysis_id} 已完成，可继续查看看板或生成报告。`;
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

function workflowStatusLabel(status: AnalysisWorkflowStatus): string {
  const labels: Record<AnalysisWorkflowStatus, string> = {
    waiting: "等待中",
    running: "运行中",
    success: "已完成",
    failed: "失败",
    fallback_used: "使用兜底",
  };
  return labels[status];
}

function evidenceCardClassName(tone: EvidenceCard["tone"]): string {
  const classNames: Record<EvidenceCard["tone"], string> = {
    api: "border-river/20 bg-river/5",
    csv: "border-wheat/40 bg-wheat/10",
    ai: "border-jade/20 bg-jade/10",
  };
  return classNames[tone];
}

function summarizeLabels(labels: Set<string>): string {
  const values = Array.from(labels).filter(Boolean);
  if (values.length === 0) {
    return "-";
  }
  const visible = values.slice(0, 4).join("、");
  return values.length > 4 ? `${visible} 等 ${values.length} 项来源` : visible;
}

function readSourceString(source: Record<string, unknown>, key: string): string {
  const value = source[key];
  return typeof value === "string" ? value : "";
}

function readSourceBoolean(source: Record<string, unknown>, key: string): boolean {
  return source[key] === true;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
