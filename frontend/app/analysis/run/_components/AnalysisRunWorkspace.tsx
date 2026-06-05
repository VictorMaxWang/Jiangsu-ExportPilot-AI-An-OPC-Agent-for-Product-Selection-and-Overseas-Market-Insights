"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentFlowTimeline, AGENT_NODE_LABELS, AGENT_STEP_LABELS } from "../../../../components/agent-flow";
import { EmptyState } from "../../../_components/EmptyState";
import { ErrorState } from "../../../_components/ErrorState";
import { FallbackNotice } from "../../../_components/FallbackNotice";
import { LoadingState } from "../../../_components/LoadingState";
import { useI18n } from "../../../_components/LanguageProvider";
import {
  AnalysisCountryPresetCatalogItem,
  AnalysisPerformanceResponse,
  AnalysisStatusResponse,
  AnalysisStepLog,
  AnalysisWorkflowStatus,
  Company,
  Product,
  ProductDraft,
  generateReport,
  getAnalysisPerformance,
  getAnalysisStatus,
  getFriendlyErrorMessage,
  listProductIntakeDrafts,
  listMarketPresets,
  listCompanies,
  listProducts,
  listTargetCountries,
  startAnalysisRun,
  TargetCountryCatalogItem,
} from "../../../_lib/api-client";

const POLL_INTERVAL_MS = 1500;
const DEMO_PRODUCT_COUNT = 3;
const DEFAULT_COMPETITOR_LIMIT = 20;
const MAX_TARGET_COUNTRIES = 20;

const STEP_IDS = Object.keys(AGENT_STEP_LABELS);

type TextFn = (zh: string, en?: string) => string;

type CountryGroupKey = "asia" | "europe" | "north_america" | "latam" | "oceania" | "africa";

type CountryGroupDefinition = {
  key: CountryGroupKey;
  labelZh: string;
  labelEn: string;
};

type CountryGroup = CountryGroupDefinition & {
  items: TargetCountryCatalogItem[];
};

const COUNTRY_GROUPS: CountryGroupDefinition[] = [
  { key: "asia", labelZh: "亚洲", labelEn: "Asia" },
  { key: "europe", labelZh: "欧洲", labelEn: "Europe" },
  { key: "north_america", labelZh: "北美", labelEn: "North America" },
  { key: "latam", labelZh: "拉美", labelEn: "Latin America" },
  { key: "oceania", labelZh: "大洋洲", labelEn: "Oceania" },
  { key: "africa", labelZh: "非洲", labelEn: "Africa" },
];

type EvidenceCard = {
  key: string;
  title: string;
  status: string;
  detail: string;
  tone: "api" | "csv" | "ai";
};

export function AnalysisRunWorkspace() {
  const router = useRouter();
  const { text } = useI18n();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [recentIntakeDrafts, setRecentIntakeDrafts] = useState<ProductDraft[]>([]);
  const [targetCountries, setTargetCountries] = useState<TargetCountryCatalogItem[]>([]);
  const [countryPresets, setCountryPresets] = useState<AnalysisCountryPresetCatalogItem[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [selectedCountryCodes, setSelectedCountryCodes] = useState<string[]>([]);
  const [competitorLimit, setCompetitorLimit] = useState(DEFAULT_COMPETITOR_LIMIT);
  const [loading, setLoading] = useState(true);
  const [productsLoading, setProductsLoading] = useState(false);
  const [intakeDraftsLoading, setIntakeDraftsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatusResponse | null>(null);
  const [analysisPerformance, setAnalysisPerformance] = useState<AnalysisPerformanceResponse | null>(null);
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [lastStatusUpdatedAt, setLastStatusUpdatedAt] = useState<Date | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const runTokenRef = useRef(0);
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
    setSubmitting(false);
    setGeneratingReport(false);
    setAnalysisStatus(null);
    setAnalysisPerformance(null);
    setAnalysisId(null);
    setLastStatusUpdatedAt(null);
    setNow(Date.now());
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

  const availableTargetCountries = useMemo(
    () => targetCountries.filter((country) => country.enabled && country.analysis_enabled),
    [targetCountries],
  );

  const countriesByCode = useMemo(
    () => new Map(availableTargetCountries.map((country) => [country.country_code, country])),
    [availableTargetCountries],
  );

  const countryGroups = useMemo(() => buildCountryGroups(availableTargetCountries), [availableTargetCountries]);

  const matchedPreset = useMemo(
    () => countryPresets.find((preset) => sameCountrySet(preset.country_codes, selectedCountryCodes)) ?? null,
    [countryPresets, selectedCountryCodes],
  );

  const currentPresetName = matchedPreset ? presetDisplayName(matchedPreset, text) : text("自定义组合", "Custom set");
  const selectedCountryCount = selectedCountryCodes.length;
  const countrySelectionInvalid = selectedCountryCount === 0 || selectedCountryCount > MAX_TARGET_COUNTRIES;
  const countryCatalogReady = availableTargetCountries.length > 0;
  const analysisCombinationCount = selectedProductIds.length * selectedCountryCount;

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
  const completedStepCount = countCompletedSteps(timelineSteps);
  const currentStepLabel = currentStepDisplay(analysisStatus, timelineSteps);
  const totalRunDurationMs = analysisPerformance?.duration_ms ?? runDurationMs(analysisStatus, now);
  const dashboardReady = Boolean(analysisStatus && analysisStatus.scoring_summary.item_count > 0);
  const reportPending = dashboardReady && !isStepComplete(timelineSteps, "09_report_prep");

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
      const [companyResponse, countryResponse, presetResponse] = await Promise.all([
        listCompanies(),
        listTargetCountries(),
        listMarketPresets(),
      ]);
      setCompanies(companyResponse.items);
      setTargetCountries(countryResponse.items);
      setCountryPresets(presetResponse.items);
      const firstCompany = companyResponse.items[0] ?? null;
      setSelectedCompanyId(firstCompany?.id ?? null);
      setSelectedCountryCodes(defaultCountryCodes(countryResponse.items, presetResponse.items));
      setCompetitorLimit(DEFAULT_COMPETITOR_LIMIT);
      if (firstCompany) {
        await Promise.all([loadProducts(firstCompany.id, true), loadRecentIntakeDrafts(firstCompany.id)]);
      } else {
        setProducts([]);
        setSelectedProductIds([]);
        setRecentIntakeDrafts([]);
      }
    } catch (requestError) {
      setTargetCountries([]);
      setCountryPresets([]);
      setSelectedCountryCodes([]);
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

  useEffect(() => {
    if (!submitting && (!analysisStatus || terminal)) {
      return undefined;
    }
    const intervalId = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(intervalId);
    };
  }, [analysisStatus, submitting, terminal]);

  function handleCompanyChange(value: string) {
    const companyId = value ? Number(value) : null;
    resetRunState();
    setSelectedCompanyId(companyId);
    setSelectedProductIds([]);
    setSelectedCountryCodes(defaultCountryCodes(targetCountries, countryPresets));
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
      setError(text("请先创建企业，再使用推荐演示配置。", "Create a company before applying demo settings."));
      return;
    }
    resetRunState();
    setSelectedCompanyId(demoCompany.id);
    const demoCountries = defaultCountryCodes(targetCountries, countryPresets);
    setSelectedCountryCodes(demoCountries);
    setCompetitorLimit(DEFAULT_COMPETITOR_LIMIT);
    await Promise.all([loadProducts(demoCompany.id, true), loadRecentIntakeDrafts(demoCompany.id)]);
    const demoPreset = countryPresets.find((preset) => sameCountrySet(preset.country_codes, demoCountries)) ?? null;
    const demoPresetName = demoPreset ? presetDisplayName(demoPreset, text) : demoCountries.join(", ");
    setNotice(
      text(
        `已应用推荐演示配置：首个企业、前 3 个产品、${demoPresetName} 和 20 条竞品采集上限。`,
        `Applied demo settings: first company, first 3 products, ${demoPresetName}, and 20 competitor samples.`,
      ),
    );
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

  function applyCountryPreset(preset: AnalysisCountryPresetCatalogItem) {
    const nextCodes = countryCodesFromPreset(preset, countriesByCode);
    if (nextCodes.length === 0) {
      setError(text("该预设的国家当前不可用于分析。", "The countries in this preset are not currently available for analysis."));
      return;
    }
    resetRunState();
    setSelectedCountryCodes(nextCodes);
  }

  function toggleCountry(countryCode: string, checked: boolean) {
    if (checked && !selectedCountryCodes.includes(countryCode) && selectedCountryCodes.length >= MAX_TARGET_COUNTRIES) {
      setError(
        text(
          `目标国家最多选择 ${MAX_TARGET_COUNTRIES} 个。`,
          `Select at most ${MAX_TARGET_COUNTRIES} target countries.`,
        ),
      );
      return;
    }
    resetRunState();
    setSelectedCountryCodes((current) => {
      if (!checked) {
        return current.filter((code) => code !== countryCode);
      }
      if (current.includes(countryCode)) {
        return current;
      }
      return [...current, countryCode];
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

    if (!countryCatalogReady) {
      setError(text("目标国家目录未加载，无法启动分析。", "Target country catalog is not loaded, so analysis cannot start."));
      return;
    }

    if (selectedCountryCodes.length === 0) {
      setError(text("请至少选择一个目标国家。", "Select at least one target country."));
      return;
    }

    if (selectedCountryCodes.length > MAX_TARGET_COUNTRIES) {
      setError(
        text(
          `目标国家最多选择 ${MAX_TARGET_COUNTRIES} 个。`,
          `Select at most ${MAX_TARGET_COUNTRIES} target countries.`,
        ),
      );
      return;
    }

    clearPolling();
    const token = runTokenRef.current + 1;
    runTokenRef.current = token;
    setSubmitting(true);
    setAnalysisStatus(null);
    setAnalysisPerformance(null);
    setAnalysisId(null);
    setLastStatusUpdatedAt(null);
    setNow(Date.now());
    setNotice("分析任务已提交，正在等待智能体工作流接收。");

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const started = await startAnalysisRun(
        {
          company_id: selectedCompanyId,
          product_ids: productIds,
          target_countries: selectedCountryCodes,
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
      const [status, performance] = await Promise.all([
        getAnalysisStatus(runId, controller.signal),
        getAnalysisPerformance(runId, controller.signal),
      ]);
      if (token !== runTokenRef.current) {
        return;
      }

      setAnalysisStatus(status);
      setAnalysisPerformance(performance);
      setLastStatusUpdatedAt(new Date());
      setNow(Date.now());
      if (isTerminalStatus(status.status) || status.finished_at) {
        setSubmitting(false);
        setNotice(buildTerminalNotice(status));
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
            <LoadingState label={text("正在加载企业、产品和目标国家目录", "Loading companies, products, and target country catalog")} rows={4} />
          ) : error && companies.length === 0 ? (
            <ErrorState message={error} />
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
                  <p className="text-sm font-semibold text-ink">{text("推荐演示配置", "Recommended demo settings")}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">
                    {text(
                      `首个企业、前 3 个产品、${currentPresetName}，适合 5 分钟现场演示。`,
                      `First company, first 3 products, and ${currentPresetName}; suitable for a 5-minute demo.`,
                    )}
                  </p>
                </div>
                <button
                  className="rounded-md border border-river/30 bg-white px-3 py-2 text-sm font-semibold text-river disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={productsLoading || submitting || !countryCatalogReady}
                  type="button"
                  onClick={() => void applyRecommendedDemoConfig()}
                >
                  {text("使用推荐演示配置", "Use demo settings")}
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

              <section className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-ink">{text("选择目标国家", "Choose target countries")}</h3>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      {text(
                        "国家目录和预设来自后端市场目录接口，可按洲/区域快速组合。",
                        "Countries and presets come from the backend market catalog and can be combined by region.",
                      )}
                    </p>
                  </div>
                  <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${
                    countrySelectionInvalid ? "bg-red-50 text-red-700 ring-red-200" : "bg-jade/10 text-jade ring-jade/20"
                  }`}>
                    {selectedCountryCount}/{MAX_TARGET_COUNTRIES}
                  </span>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricReadout
                    label={text("已选国家", "Selected countries")}
                    value={`${selectedCountryCount}/${MAX_TARGET_COUNTRIES}`}
                  />
                  <MetricReadout label={text("可选国家", "Available countries")} value={availableTargetCountries.length} />
                  <MetricReadout label={text("当前预设", "Current preset")} value={currentPresetName} />
                  <MetricReadout label={text("预计分析组合", "Analysis combinations")} value={analysisCombinationCount} />
                </div>

                {countryPresets.length > 0 ? (
                  <div className="grid gap-2">
                    <p className="text-xs font-semibold text-slate-500">{text("快捷预设", "Quick presets")}</p>
                    <div className="flex flex-wrap gap-2">
                      {countryPresets.map((preset) => {
                        const active = sameCountrySet(preset.country_codes, selectedCountryCodes);
                        return (
                          <button
                            key={preset.preset_code}
                            className={`rounded-md border px-3 py-2 text-left text-xs font-semibold transition ${
                              active
                                ? "border-river bg-river text-white"
                                : "border-slate-200 bg-slate-50 text-slate-700 hover:border-river/40 hover:bg-river/5"
                            }`}
                            disabled={submitting || !countryCatalogReady}
                            type="button"
                            onClick={() => applyCountryPreset(preset)}
                          >
                            <span className="block">{presetDisplayName(preset, text)}</span>
                            <span className={`mt-1 block font-medium ${active ? "text-white/80" : "text-slate-500"}`}>
                              {preset.country_codes.length} {text("个国家", "countries")}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {countryCatalogReady ? (
                  <div className="grid gap-3">
                    {countryGroups.map((group) => (
                      <CountryGroupPanel
                        key={group.key}
                        group={group}
                        maxSelected={MAX_TARGET_COUNTRIES}
                        selectedCodes={selectedCountryCodes}
                        text={text}
                        onToggle={toggleCountry}
                      />
                    ))}
                  </div>
                ) : (
                  <ErrorState message={text("目标国家目录未加载，无法选择国家。", "Target country catalog is not loaded.")} />
                )}
              </section>

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

              <p className="rounded-lg border border-wheat/40 bg-wheat/10 p-3 text-sm font-medium leading-6 text-ink">
                {text(
                  "目标国家越多，数据采集和 AI 解释耗时越长；系统会自动优先使用缓存，必要时启用公开数据、CSV 或 AI fallback。",
                  "More target countries take longer for data collection and AI explanation; the system prioritizes cache and uses public data, CSV, or AI fallback when needed.",
                )}
              </p>

              <button
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={
                  submitting ||
                  productsLoading ||
                  !selectedCompanyId ||
                  selectedProductIds.length === 0 ||
                  !countryCatalogReady ||
                  countrySelectionInvalid
                }
                type="submit"
              >
                {submitting ? text("智能体分析中", "Analyzing") : text("开始智能体分析", "Start agent analysis")}
              </button>
            </form>
          )}
        </Panel>

        <Panel title="当前任务">
          <div className="grid gap-3">
            <DetailItem label="分析 ID" value={analysisId ? `#${analysisId}` : "-"} />
            <DetailItem label="企业" value={selectedCompany?.name ?? "-"} />
            <DetailItem label="产品" value={selectedProductsLabel(selectedProducts)} />
            <DetailItem label="目标国家" value={selectedCountryCodes.join(", ") || "-"} />
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
            {dashboardReady ? (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Link
                  className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white"
                  href={`/dashboard/${analysisStatus.analysis_id}`}
                >
                  {text("查看当前看板", "View current dashboard")}
                </Link>
                {terminal && analysisStatus.status !== "failed" ? (
                  <button
                    className="rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                    disabled={generatingReport}
                    type="button"
                    onClick={() => void handleGenerateReport()}
                  >
                    {generatingReport ? "生成中" : "生成报告"}
                  </button>
                ) : null}
              </div>
            ) : null}
            {reportPending ? (
              <p className="mt-3 rounded-lg border border-river/20 bg-river/5 p-3 text-sm font-medium leading-6 text-river">
                {text("报告可稍后生成，不影响看板查看", "The report can be generated later and does not block dashboard viewing.")}
              </p>
            ) : null}
          </Panel>
        ) : null}
      </section>

      <section className="grid gap-5">
        <Panel title="智能体协作分析">
          <ProgressOverview
            completedStepCount={completedStepCount}
            currentStepLabel={currentStepLabel}
            lastStatusUpdatedAt={lastStatusUpdatedAt}
            status={analysisStatus?.status ?? "waiting"}
            text={text}
            totalRunDurationMs={totalRunDurationMs}
            totalStepCount={STEP_IDS.length}
          />
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-ink">9 个后端智能体按顺序执行</p>
              <p className="mt-1 text-xs text-slate-500">每 {POLL_INTERVAL_MS / 1000} 秒读取一次状态，完成后停留在本页供评委选择下一步。</p>
            </div>
            <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${overallStatusClassName(analysisStatus?.status ?? "waiting")}`}>
              {workflowStatusLabel(analysisStatus?.status ?? "waiting")}
            </span>
          </div>
          <AgentFlowTimeline
            currentStepId={analysisStatus?.current_step}
            now={now}
            performanceSteps={analysisPerformance?.steps}
            steps={timelineSteps}
          />
          <PerformanceSlowPoints performance={analysisPerformance} steps={timelineSteps} text={text} now={now} />
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

function MetricReadout({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-h-[82px] rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-2 truncate text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function CountryGroupPanel({
  group,
  maxSelected,
  selectedCodes,
  text,
  onToggle,
}: {
  group: CountryGroup;
  maxSelected: number;
  selectedCodes: string[];
  text: TextFn;
  onToggle: (countryCode: string, checked: boolean) => void;
}) {
  const selectedInGroup = group.items.filter((country) => selectedCodes.includes(country.country_code)).length;
  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-ink">{text(group.labelZh, group.labelEn)}</h4>
        <span className="text-xs font-semibold text-slate-500">
          {selectedInGroup}/{group.items.length}
        </span>
      </div>
      {group.items.length === 0 ? (
        <p className="mt-3 text-xs text-slate-500">{text("暂无可选国家", "No available countries")}</p>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {group.items.map((country) => {
            const checked = selectedCodes.includes(country.country_code);
            const disabled = !checked && selectedCodes.length >= maxSelected;
            return (
              <label
                key={country.country_code}
                className={`grid min-h-[72px] grid-cols-[auto_1fr] gap-3 rounded-md border px-3 py-2 text-sm transition ${
                  checked
                    ? "border-river/40 bg-white shadow-sm"
                    : "border-slate-200 bg-white/70 hover:border-river/30 hover:bg-white"
                } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <input
                  checked={checked}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-river focus:ring-river"
                  disabled={disabled}
                  type="checkbox"
                  onChange={(event) => onToggle(country.country_code, event.target.checked)}
                />
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-ink">{countryDisplayName(country, text)}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-semibold text-slate-500">
                      {country.country_code}
                    </span>
                  </span>
                  <span className="mt-1 block truncate text-xs text-slate-500">
                    {countryRegionLabel(country, text)}
                    {country.currency_code ? ` · ${country.currency_code}` : ""}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      )}
    </section>
  );
}

function ProgressOverview({
  completedStepCount,
  currentStepLabel,
  lastStatusUpdatedAt,
  status,
  text,
  totalRunDurationMs,
  totalStepCount,
}: {
  completedStepCount: number;
  currentStepLabel: string;
  lastStatusUpdatedAt: Date | null;
  status: AnalysisWorkflowStatus;
  text: (zh: string, en?: string) => string;
  totalRunDurationMs: number | null;
  totalStepCount: number;
}) {
  return (
    <div className="mb-4 grid gap-3 rounded-lg border border-river/20 bg-river/5 p-4 sm:grid-cols-2 xl:grid-cols-4">
      <ProgressMetric
        label={text("已完成", "Completed")}
        value={text(`${completedStepCount}/${totalStepCount}`, `${completedStepCount}/${totalStepCount}`)}
      />
      <ProgressMetric label={text("当前步骤", "Current step")} value={currentStepLabel} />
      <ProgressMetric label={text("总运行时间", "Total runtime")} value={formatDuration(totalRunDurationMs)} />
      <ProgressMetric
        label={text("最近一次状态更新时间", "Last status update")}
        value={formatDateTimeFromDate(lastStatusUpdatedAt)}
      />
      <div className="sm:col-span-2 xl:col-span-4">
        <span className={`inline-flex rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${overallStatusClassName(status)}`}>
          {workflowStatusLabel(status, text)}
        </span>
      </div>
    </div>
  );
}

function ProgressMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-river/80">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function PerformanceSlowPoints({
  performance,
  steps,
  text,
  now,
}: {
  performance: AnalysisPerformanceResponse | null;
  steps: AnalysisStepLog[];
  text: (zh: string, en?: string) => string;
  now: number;
}) {
  const rows = buildSlowPointRows(performance, steps, now);
  return (
    <section className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{text("性能慢点", "Performance slow spots")}</h3>
        <span className="text-xs text-slate-500">
          {text("来自 /api/analysis/{id}/performance 的安全聚合字段", "Safe aggregate fields from /api/analysis/{id}/performance")}
        </span>
      </div>
      {rows.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">{text("等待性能数据。", "Waiting for performance data.")}</p>
      ) : (
        <div className="mt-3 grid gap-2">
          {rows.map((row) => (
            <article key={row.stepId} className="rounded-md border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-ink">{row.title}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {text("状态", "Status")}：{workflowStatusLabel(row.status, text)} · duration_ms：{formatMilliseconds(row.durationMs)}
                  </p>
                </div>
                <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${overallStatusClassName(row.status)}`}>
                  {workflowStatusLabel(row.status, text)}
                </span>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-5">
                <ProgressMetric label="provider" value={String(row.providerCallCount)} />
                <ProgressMetric label="qwen" value={String(row.qwenCallCount)} />
                <ProgressMetric label="cache" value={String(row.cacheHitCount)} />
                <ProgressMetric label="fallback" value={String(row.fallbackCount)} />
                <ProgressMetric label="timeout" value={String(row.timeoutCount)} />
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
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

type SlowPointRow = {
  stepId: string;
  title: string;
  status: AnalysisWorkflowStatus;
  durationMs: number | null;
  providerCallCount: number;
  qwenCallCount: number;
  cacheHitCount: number;
  fallbackCount: number;
  timeoutCount: number;
};

function buildSlowPointRows(
  performance: AnalysisPerformanceResponse | null,
  steps: AnalysisStepLog[],
  now: number,
): SlowPointRow[] {
  const performanceByStepId = new Map((performance?.steps ?? []).map((step) => [step.step_id, step]));
  return steps
    .map((step) => {
      const performanceStep = performanceByStepId.get(step.step_id);
      const durationMs =
        performanceStep?.duration_ms ??
        step.duration_ms ??
        (step.status === "running" ? elapsedSince(step.started_at, now) : null);
      const row: SlowPointRow = {
        stepId: step.step_id,
        title: AGENT_STEP_LABELS[step.step_id] ?? step.title,
        status: step.status,
        durationMs,
        providerCallCount: performanceStep?.provider_call_count ?? step.provider_call_count,
        qwenCallCount: performanceStep?.qwen_call_count ?? step.qwen_call_count,
        cacheHitCount: performanceStep?.cache_hit_count ?? step.cache_hit_count,
        fallbackCount: performanceStep?.fallback_count ?? step.fallback_count,
        timeoutCount: performanceStep?.timeout_count ?? step.timeout_count,
      };
      return row;
    })
    .filter((row) => row.durationMs !== null || slowPointCountTotal(row) > 0)
    .sort((left, right) => {
      const durationDelta = (right.durationMs ?? 0) - (left.durationMs ?? 0);
      if (durationDelta !== 0) {
        return durationDelta;
      }
      return slowPointCountTotal(right) - slowPointCountTotal(left);
    })
    .slice(0, 4);
}

function slowPointCountTotal(row: SlowPointRow): number {
  return row.providerCallCount + row.qwenCallCount + row.cacheHitCount + row.fallbackCount + row.timeoutCount;
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

function defaultCountryCodes(
  countries: TargetCountryCatalogItem[],
  presets: AnalysisCountryPresetCatalogItem[],
): string[] {
  const countryMap = new Map(availableCountries(countries).map((country) => [country.country_code, country]));
  const defaultPreset = presets.find((preset) => preset.is_default) ?? presets[0] ?? null;
  if (defaultPreset) {
    const presetCodes = countryCodesFromPreset(defaultPreset, countryMap);
    if (presetCodes.length > 0) {
      return presetCodes;
    }
  }
  return Array.from(countryMap.keys()).slice(0, MAX_TARGET_COUNTRIES);
}

function availableCountries(countries: TargetCountryCatalogItem[]): TargetCountryCatalogItem[] {
  return countries.filter((country) => country.enabled && country.analysis_enabled);
}

function countryCodesFromPreset(
  preset: AnalysisCountryPresetCatalogItem,
  countriesByCode: Map<string, TargetCountryCatalogItem>,
): string[] {
  return normalizeCountryCodes(preset.country_codes)
    .filter((countryCode) => countriesByCode.has(countryCode))
    .slice(0, MAX_TARGET_COUNTRIES);
}

function normalizeCountryCodes(values: string[]): string[] {
  const seen = new Set<string>();
  return values
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

function sameCountrySet(left: string[], right: string[]): boolean {
  const normalizedLeft = normalizeCountryCodes(left);
  const normalizedRight = normalizeCountryCodes(right);
  if (normalizedLeft.length !== normalizedRight.length) {
    return false;
  }
  const rightSet = new Set(normalizedRight);
  return normalizedLeft.every((countryCode) => rightSet.has(countryCode));
}

function buildCountryGroups(countries: TargetCountryCatalogItem[]): CountryGroup[] {
  const itemsByGroup = new Map<CountryGroupKey, TargetCountryCatalogItem[]>(
    COUNTRY_GROUPS.map((group): [CountryGroupKey, TargetCountryCatalogItem[]] => [group.key, []]),
  );
  for (const country of countries) {
    const groupKey = countryGroupKey(country);
    if (groupKey) {
      itemsByGroup.get(groupKey)?.push(country);
    }
  }
  return COUNTRY_GROUPS.map((group) => ({
    ...group,
    items: itemsByGroup.get(group.key) ?? [],
  }));
}

function countryGroupKey(country: TargetCountryCatalogItem): CountryGroupKey | null {
  if (country.continent === "Asia") {
    return "asia";
  }
  if (country.continent === "Europe") {
    return "europe";
  }
  if (country.continent === "North America") {
    return "north_america";
  }
  if (country.region_code === "LATAM" || country.continent === "South America") {
    return "latam";
  }
  if (country.continent === "Oceania") {
    return "oceania";
  }
  if (country.continent === "Africa") {
    return "africa";
  }
  return null;
}

function presetDisplayName(preset: AnalysisCountryPresetCatalogItem, text: TextFn): string {
  return text(preset.name_cn, preset.name_en ?? preset.name_cn);
}

function countryDisplayName(country: TargetCountryCatalogItem, text: TextFn): string {
  return text(country.name_cn, country.name_en);
}

function countryRegionLabel(country: TargetCountryCatalogItem, text: TextFn): string {
  return text(country.region_name_cn ?? country.region_code, country.region_name_en ?? country.region_code);
}

function isTerminalStatus(status: AnalysisWorkflowStatus): boolean {
  return status === "success" || status === "failed" || status === "fallback_used";
}

function countCompletedSteps(steps: AnalysisStepLog[]): number {
  return steps.filter((step) => isStepCompleteStatus(step.status)).length;
}

function isStepComplete(steps: AnalysisStepLog[], stepId: string): boolean {
  return steps.some((step) => step.step_id === stepId && isStepCompleteStatus(step.status));
}

function isStepCompleteStatus(status: AnalysisWorkflowStatus): boolean {
  return status === "success" || status === "fallback_used";
}

function currentStepDisplay(status: AnalysisStatusResponse | null, steps: AnalysisStepLog[]): string {
  if (!status) {
    return "等待开始";
  }
  if (status.status === "failed") {
    const failedStep = steps.find((step) => step.status === "failed");
    return failedStep ? AGENT_STEP_LABELS[failedStep.step_id] ?? failedStep.title : "失败步骤";
  }
  if (isTerminalStatus(status.status)) {
    return "全部步骤已结束";
  }
  const currentStep = steps.find((step) => step.step_id === status.current_step);
  return currentStep ? AGENT_STEP_LABELS[currentStep.step_id] ?? currentStep.title : "等待后端更新";
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

function runDurationMs(status: AnalysisStatusResponse | null, now: number): number | null {
  if (!status?.started_at) {
    return null;
  }
  const startedAt = new Date(status.started_at).getTime();
  const finishedAt = status.finished_at ? new Date(status.finished_at).getTime() : now;
  if (!Number.isFinite(startedAt) || !Number.isFinite(finishedAt)) {
    return null;
  }
  return Math.max(0, finishedAt - startedAt);
}

function elapsedSince(value: string | null | undefined, now: number): number | null {
  if (!value) {
    return null;
  }
  const startedAt = new Date(value).getTime();
  if (!Number.isFinite(startedAt)) {
    return null;
  }
  return Math.max(0, now - startedAt);
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

function formatMilliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value} ms`;
}

function formatDateTimeFromDate(value: Date | null): string {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(value);
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

function workflowStatusLabel(status: AnalysisWorkflowStatus, localize?: (zh: string, en?: string) => string): string {
  const labels: Record<AnalysisWorkflowStatus, [string, string]> = {
    waiting: ["等待中", "Waiting"],
    running: ["运行中", "Running"],
    success: ["已完成", "Completed"],
    failed: ["失败", "Failed"],
    fallback_used: ["使用兜底", "Fallback used"],
  };
  const [zh, en] = labels[status];
  return localize ? localize(zh, en) : zh;
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
