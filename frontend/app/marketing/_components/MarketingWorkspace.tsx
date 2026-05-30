"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import {
  AnalysisDetailResponse,
  AnalysisScoreItem,
  MarketingGenerateResponse,
  generateMarketingContent,
  getAnalysisDetail,
  getFriendlyErrorMessage,
} from "../../_lib/api-client";

type InputMode = "analysis" | "manual";

type FormState = {
  product: string;
  country: string;
  targetUsers: string;
  sellingPoints: string;
  priceRange: string;
  contentThemes: string;
  riskNotes: string;
};

type OutputSection = {
  key: string;
  title: string;
  text: string;
};

const emptyForm: FormState = {
  product: "",
  country: "US",
  targetUsers: "",
  sellingPoints: "",
  priceRange: "",
  contentThemes: "",
  riskNotes: "",
};

export function MarketingWorkspace() {
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<InputMode>("manual");
  const [analysisIdInput, setAnalysisIdInput] = useState(searchParams.get("analysis_id") ?? "");
  const [analysisDetail, setAnalysisDetail] = useState<AnalysisDetailResponse | null>(null);
  const [selectedScoreKey, setSelectedScoreKey] = useState("");
  const [form, setForm] = useState<FormState>(emptyForm);
  const [result, setResult] = useState<MarketingGenerateResponse | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [aiFallbackNotice, setAiFallbackNotice] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const loadAnalysisById = useCallback(async (rawId: string) => {
    const analysisId = Number(rawId);
    if (!Number.isInteger(analysisId) || analysisId < 1) {
      setError("请输入有效的分析 ID。");
      return;
    }

    setMode("analysis");
    setLoadingAnalysis(true);
    setError(null);
    setNotice(null);
    setAiFallbackNotice(null);
    try {
      const detail = await getAnalysisDetail(analysisId);
      setAnalysisDetail(detail);
      const topEntry = topScoreEntry(detail.scores);
      if (topEntry) {
        const nextForm = formFromScore(topEntry.score, detail);
        const asset = matchingMarketingAsset(topEntry.score, detail);
        setSelectedScoreKey(scoreKey(topEntry.score, topEntry.index));
        setForm(nextForm);
        setResult(asset ? marketingResultFromAsset(asset, nextForm) : null);
        setNotice(
          asset
            ? `分析 #${analysisId} 已加载，并自动展示最高推荐项的随分析营销草稿。`
            : `分析 #${analysisId} 已加载，并自动填入最高推荐项。`,
        );
      } else {
        setSelectedScoreKey("");
        setResult(null);
        setNotice(`分析 #${analysisId} 已加载，但未找到评分行。`);
      }
    } catch (requestError) {
      setAnalysisDetail(null);
      setSelectedScoreKey("");
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setLoadingAnalysis(false);
    }
  }, []);

  useEffect(() => {
    const queryId = searchParams.get("analysis_id");
    if (queryId) {
      setAnalysisIdInput(queryId);
      void loadAnalysisById(queryId);
    }
  }, [loadAnalysisById, searchParams]);

  const selectedScore = useMemo(() => {
    if (!analysisDetail) {
      return null;
    }
    return (
      analysisDetail.scores.find((score, index) => scoreKey(score, index) === selectedScoreKey) ??
      topScoreEntry(analysisDetail.scores)?.score ??
      null
    );
  }, [analysisDetail, selectedScoreKey]);

  const outputSections = useMemo(() => (result ? buildOutputSections(result) : []), [result]);

  function handleScoreChange(value: string) {
    setSelectedScoreKey(value);
    const score = analysisDetail?.scores.find((item, index) => scoreKey(item, index) === value) ?? null;
    if (score && analysisDetail) {
      const nextForm = formFromScore(score, analysisDetail);
      const asset = matchingMarketingAsset(score, analysisDetail);
      setForm(nextForm);
      setResult(asset ? marketingResultFromAsset(asset, nextForm) : null);
      setAiFallbackNotice(null);
      setNotice(asset ? "已加载该分析行保存的营销草稿。" : "已将该分析行填入生成器。");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setCopyError(null);
    setAiFallbackNotice(null);

    const normalizedCountry = form.country.trim().toUpperCase();
    if (!form.product.trim()) {
      setError("请填写产品。");
      return;
    }
    if (!/^[A-Z]{2,3}$/.test(normalizedCountry)) {
      setError("国家必须是 2 或 3 位代码，例如 US、JP 或 GB。");
      return;
    }

    setGenerating(true);
    try {
      const generated = await generateMarketingContent({
        product: form.product.trim(),
        country: normalizedCountry,
        target_users: splitList(form.targetUsers),
        selling_points: splitList(form.sellingPoints),
        price_range: optionalText(form.priceRange),
        content_themes: splitList(form.contentThemes),
        risk_notes: splitList(form.riskNotes),
        analysis_id: mode === "analysis" ? analysisDetail?.analysis_id ?? null : null,
        score_id: mode === "analysis" ? selectedScore?.id ?? null : null,
        persist_to_analysis: mode === "analysis" && Boolean(analysisDetail),
      });
      setResult(generated);
      setForm((current) => ({ ...current, country: normalizedCountry }));
      setNotice(mode === "analysis" ? "草稿已生成并保存到分析状态。" : "草稿已生成。");
    } catch (requestError) {
      const message = getFriendlyErrorMessage(requestError);
      setAiFallbackNotice(
        `AI 实时生成暂时不可用：${message}。如果右侧已有随分析生成的营销草稿，可直接复制；否则可使用已自动填入的 top recommendation 信息继续讲解。`,
      );
    } finally {
      setGenerating(false);
    }
  }

  async function copyText(key: string, text: string) {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey((current) => (current === key ? null : current)), 2000);
    } catch {
      setCopyError("复制到剪贴板失败，请手动选择文本复制。");
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="grid gap-5">
        <Panel title="来源">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
              <button
                className={`rounded-md px-3 py-2 text-sm font-semibold ${mode === "analysis" ? "bg-white text-river shadow-sm" : "text-slate-600"}`}
                type="button"
                onClick={() => setMode("analysis")}
              >
                分析结果
              </button>
              <button
                className={`rounded-md px-3 py-2 text-sm font-semibold ${mode === "manual" ? "bg-white text-river shadow-sm" : "text-slate-600"}`}
                type="button"
                onClick={() => setMode("manual")}
              >
                手动输入
              </button>
            </div>

            {mode === "analysis" ? (
              <div className="grid gap-4">
                <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                  <TextInput
                    label="分析 ID"
                    value={analysisIdInput}
                    onChange={setAnalysisIdInput}
                  />
                  <button
                    className="self-end rounded-md border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                    disabled={loadingAnalysis || !analysisIdInput.trim()}
                    type="button"
                    onClick={() => void loadAnalysisById(analysisIdInput)}
                  >
                    {loadingAnalysis ? "加载中" : "加载"}
                  </button>
                </div>
                {loadingAnalysis ? <LoadingState label="正在加载分析上下文" rows={3} /> : null}
                {analysisDetail && analysisDetail.scores.length > 0 ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-medium text-slate-700">产品-国家评分行</span>
                    <select
                      className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                      value={selectedScoreKey}
                      onChange={(event) => handleScoreChange(event.target.value)}
                    >
                      {analysisDetail.scores.map((score, index) => (
                        <option key={scoreKey(score, index)} value={scoreKey(score, index)}>
                          {score.rank ? `#${score.rank} ` : ""}
                          {score.product_name_en || score.product_name_cn} / {score.country}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel title="生成输入">
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <TextInput label="产品" required value={form.product} onChange={(value) => setForm({ ...form, product: value })} />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput label="国家" required value={form.country} onChange={(value) => setForm({ ...form, country: value })} />
              <TextInput label="价格区间" value={form.priceRange} onChange={(value) => setForm({ ...form, priceRange: value })} />
            </div>
            <TextArea label="目标用户" value={form.targetUsers} onChange={(value) => setForm({ ...form, targetUsers: value })} />
            <TextArea label="卖点" value={form.sellingPoints} onChange={(value) => setForm({ ...form, sellingPoints: value })} />
            <TextArea label="内容主题" value={form.contentThemes} onChange={(value) => setForm({ ...form, contentThemes: value })} />
            <TextArea label="风险提示" value={form.riskNotes} onChange={(value) => setForm({ ...form, riskNotes: value })} />
            <button
              className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={generating || !form.product.trim() || !form.country.trim()}
              type="submit"
            >
              {generating ? "生成中" : "生成营销文案"}
            </button>
          </form>
        </Panel>

        {notice ? <p className="rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
        {aiFallbackNotice ? (
          <FallbackNotice
            source="mock"
            title="营销生成已切换为演示说明"
            description={aiFallbackNotice}
          />
        ) : null}
        {error ? <ErrorState message={error} /> : null}
      </section>

      <section className="grid gap-5">
        <Panel title="生成草稿">
          {generating ? (
            <LoadingState label="正在调用 qwen3.6-plus" rows={5} />
          ) : result ? (
            <div className="grid gap-4">
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
                  type="button"
                  onClick={() => void copyText("all", formatAll(result))}
                >
                  {copiedKey === "all" ? "已复制" : "复制全部"}
                </button>
              </div>
              {outputSections.map((section) => (
                <OutputBlock
                  key={section.key}
                  copied={copiedKey === section.key}
                  section={section}
                  onCopy={() => void copyText(section.key, section.text)}
                />
              ))}
              {copyError ? <ErrorState title="剪贴板" message={copyError} /> : null}
            </div>
          ) : (
            <EmptyState title="暂无草稿" description="可从分析评分行或手动产品信息生成内容。" />
          )}
        </Panel>
        <FallbackNotice
          source="sample"
          title="发布前需复核"
          description="生成文案发布前应结合平台政策、宣称证据和样本数据边界进行人工复核。"
        />
      </section>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-4 text-sm leading-6 text-slate-600">{children}</div>
    </section>
  );
}

function TextInput({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
        required={required}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <textarea
        className="min-h-24 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function OutputBlock({
  section,
  copied,
  onCopy,
}: {
  section: OutputSection;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">{section.title}</h3>
        <button
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700"
          type="button"
          onClick={onCopy}
        >
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre className="mt-3 whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-700">{section.text}</pre>
    </article>
  );
}

function topScoreEntry(scores: AnalysisScoreItem[]): { score: AnalysisScoreItem; index: number } | null {
  if (scores.length === 0) {
    return null;
  }
  return scores
    .map((score, index) => ({ score, index }))
    .sort((left, right) => {
      const leftRank = left.score.rank ?? Number.MAX_SAFE_INTEGER;
      const rightRank = right.score.rank ?? Number.MAX_SAFE_INTEGER;
      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }
      return scoreNumber(right.score.total_score) - scoreNumber(left.score.total_score);
    })[0] ?? null;
}

function matchingMarketingAsset(score: AnalysisScoreItem, detail: AnalysisDetailResponse): Record<string, unknown> | null {
  const assets = toRecordArray(detail.workflow_state.marketing_assets);
  return (
    assets.find((asset) => {
      const assetScoreId = Number(asset.score_id);
      if (score.id && assetScoreId === score.id) {
        return true;
      }
      const assetProductId = Number(asset.product_id);
      const assetCountry = readString(asset.country).toUpperCase();
      const assetProduct = readString(asset.product).toLowerCase();
      const scoreProduct = (score.product_name_en || score.product_name_cn || score.keyword).toLowerCase();
      return assetCountry === score.country.toUpperCase() && (assetProductId === score.product_id || assetProduct === scoreProduct);
    }) ?? null
  );
}

function marketingResultFromAsset(asset: Record<string, unknown>, fallbackForm: FormState): MarketingGenerateResponse {
  const seoKeywords = toStringArray(asset.seo_keywords);
  const socialPosts = toStringArray(asset.social_posts);
  const localizationNotes = toStringArray(asset.localization_notes);
  const riskNotes = toStringArray(asset.risk_notes);
  const shortDescription = readString(asset.short_description);
  const adCopy = readString(asset.ad_copy);
  return {
    title: readString(asset.title) || readString(asset.listing_title) || fallbackForm.product,
    bullet_points: toStringArray(asset.bullet_points),
    seo_keywords: seoKeywords,
    short_video_script: readString(asset.short_video_script) || [shortDescription, ...socialPosts].filter(Boolean).join("\n"),
    pinterest_keywords: toStringArray(asset.pinterest_keywords).length > 0 ? toStringArray(asset.pinterest_keywords) : seoKeywords,
    platform_listing_advice: readString(asset.platform_listing_advice) || [adCopy, ...localizationNotes].filter(Boolean).join("\n"),
    risk_notes: riskNotes.length > 0 ? riskNotes : splitList(fallbackForm.riskNotes),
  };
}

function formFromScore(score: AnalysisScoreItem, detail: AnalysisDetailResponse): FormState {
  const trend = matchingTrend(score, detail);
  const competitor = score.competitor_analysis;
  const priceRange = priceRangeFromCompetitor(competitor);
  const contentThemes = [
    ...toStringArray(trend?.content_themes),
    ...toStringArray(trend?.marketing_angles),
    ...toStringArray(trend?.pain_points),
  ];
  const sellingPoints = [
    score.reason,
    readString(competitor.price_suggestion),
    score.next_action,
  ].filter(Boolean);
  const riskNotes = [
    score.risk,
    evidenceFlag(score.evidence, "content_fallback_used", "内容证据使用了兜底或样本数据。"),
    evidenceFlag(score.evidence, "competitor_fallback_used", "竞品证据使用了兜底或样本数据。"),
  ].filter(Boolean);

  return {
    product: score.product_name_en || score.product_name_cn || score.keyword,
    country: score.country,
    targetUsers: "",
    sellingPoints: sellingPoints.join("\n"),
    priceRange,
    contentThemes: dedupeStrings(contentThemes).join("\n"),
    riskNotes: dedupeStrings(riskNotes).join("\n"),
  };
}

function matchingTrend(score: AnalysisScoreItem, detail: AnalysisDetailResponse): Record<string, unknown> | null {
  const trends = toRecordArray(detail.workflow_state.content_trends);
  return (
    trends.find((trend) => {
      const productId = Number(trend.product_id);
      const country = readString(trend.country).toUpperCase();
      return productId === score.product_id && country === score.country.toUpperCase();
    }) ?? null
  );
}

function buildOutputSections(result: MarketingGenerateResponse): OutputSection[] {
  return [
    { key: "title", title: "英文标题", text: result.title },
    { key: "bullets", title: "五点卖点", text: result.bullet_points.map((item) => `- ${item}`).join("\n") },
    { key: "seo", title: "SEO 关键词", text: result.seo_keywords.join(", ") },
    { key: "video", title: "短视频脚本", text: result.short_video_script },
    { key: "pinterest", title: "Pinterest 图片关键词", text: result.pinterest_keywords.join(", ") },
    { key: "listing", title: "平台上架建议", text: result.platform_listing_advice },
    { key: "risk", title: "风险提示", text: result.risk_notes.map((item) => `- ${item}`).join("\n") },
  ];
}

function formatAll(result: MarketingGenerateResponse): string {
  return buildOutputSections(result)
    .map((section) => `${section.title}\n${section.text}`)
    .join("\n\n");
}

function splitList(value: string): string[] {
  return dedupeStrings(value.split(/[,，\n;]+/).map((item) => item.trim()).filter(Boolean));
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function scoreKey(score: AnalysisScoreItem, index: number): string {
  return score.id ? `score-${score.id}` : `row-${score.product_id}-${score.country}-${index}`;
}

function priceRangeFromCompetitor(value: Record<string, unknown>): string {
  const currency = readString(value.currency);
  const minPrice = readString(value.min_price);
  const maxPrice = readString(value.max_price);
  if (minPrice && maxPrice) {
    return `${currency ? `${currency} ` : ""}${minPrice}-${maxPrice}`;
  }
  return "";
}

function evidenceFlag(evidence: Record<string, unknown>, key: string, message: string): string {
  return evidence[key] === true ? message : "";
}

function toRecordArray(value: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(readString).filter(Boolean);
}

function readString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function scoreNumber(value: string | number | null): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed) {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(trimmed);
  }
  return result;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
