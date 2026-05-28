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
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const loadAnalysisById = useCallback(async (rawId: string) => {
    const analysisId = Number(rawId);
    if (!Number.isInteger(analysisId) || analysisId < 1) {
      setError("Enter a valid analysis id.");
      return;
    }

    setMode("analysis");
    setLoadingAnalysis(true);
    setError(null);
    setNotice(null);
    try {
      const detail = await getAnalysisDetail(analysisId);
      setAnalysisDetail(detail);
      const firstScore = detail.scores[0] ?? null;
      if (firstScore) {
        setSelectedScoreKey(scoreKey(firstScore, 0));
        setForm(formFromScore(firstScore, detail));
        setNotice(`Analysis #${analysisId} loaded with ${detail.scores.length} score rows.`);
      } else {
        setSelectedScoreKey("");
        setNotice(`Analysis #${analysisId} loaded, but no score rows were found.`);
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
      analysisDetail.scores[0] ??
      null
    );
  }, [analysisDetail, selectedScoreKey]);

  const outputSections = useMemo(() => (result ? buildOutputSections(result) : []), [result]);

  function handleScoreChange(value: string) {
    setSelectedScoreKey(value);
    const score = analysisDetail?.scores.find((item, index) => scoreKey(item, index) === value) ?? null;
    if (score && analysisDetail) {
      setForm(formFromScore(score, analysisDetail));
      setResult(null);
      setNotice("Analysis row loaded into the generator.");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setCopyError(null);

    const normalizedCountry = form.country.trim().toUpperCase();
    if (!form.product.trim()) {
      setError("Product is required.");
      return;
    }
    if (!/^[A-Z]{2,3}$/.test(normalizedCountry)) {
      setError("Country must be a 2 or 3 letter code, for example US, JP, or GB.");
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
      setNotice(mode === "analysis" ? "Draft generated and saved to the analysis state." : "Draft generated.");
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
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
      setCopyError("Clipboard copy failed. Select the text manually and copy it.");
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="grid gap-5">
        <Panel title="Source">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-100 p-1">
              <button
                className={`rounded-md px-3 py-2 text-sm font-semibold ${mode === "analysis" ? "bg-white text-river shadow-sm" : "text-slate-600"}`}
                type="button"
                onClick={() => setMode("analysis")}
              >
                Analysis result
              </button>
              <button
                className={`rounded-md px-3 py-2 text-sm font-semibold ${mode === "manual" ? "bg-white text-river shadow-sm" : "text-slate-600"}`}
                type="button"
                onClick={() => setMode("manual")}
              >
                Manual input
              </button>
            </div>

            {mode === "analysis" ? (
              <div className="grid gap-4">
                <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                  <TextInput
                    label="Analysis ID"
                    value={analysisIdInput}
                    onChange={setAnalysisIdInput}
                  />
                  <button
                    className="self-end rounded-md border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                    disabled={loadingAnalysis || !analysisIdInput.trim()}
                    type="button"
                    onClick={() => void loadAnalysisById(analysisIdInput)}
                  >
                    {loadingAnalysis ? "Loading" : "Load"}
                  </button>
                </div>
                {loadingAnalysis ? <LoadingState label="Loading analysis context" rows={3} /> : null}
                {analysisDetail && analysisDetail.scores.length > 0 ? (
                  <label className="grid gap-2">
                    <span className="text-sm font-medium text-slate-700">Product-country row</span>
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

        <Panel title="Generator input">
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <TextInput label="Product" required value={form.product} onChange={(value) => setForm({ ...form, product: value })} />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput label="Country" required value={form.country} onChange={(value) => setForm({ ...form, country: value })} />
              <TextInput label="Price range" value={form.priceRange} onChange={(value) => setForm({ ...form, priceRange: value })} />
            </div>
            <TextArea label="Target users" value={form.targetUsers} onChange={(value) => setForm({ ...form, targetUsers: value })} />
            <TextArea label="Selling points" value={form.sellingPoints} onChange={(value) => setForm({ ...form, sellingPoints: value })} />
            <TextArea label="Content themes" value={form.contentThemes} onChange={(value) => setForm({ ...form, contentThemes: value })} />
            <TextArea label="Risk notes" value={form.riskNotes} onChange={(value) => setForm({ ...form, riskNotes: value })} />
            <button
              className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={generating || !form.product.trim() || !form.country.trim()}
              type="submit"
            >
              {generating ? "Generating" : "Generate marketing content"}
            </button>
          </form>
        </Panel>

        {notice ? <p className="rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
        {error ? <ErrorState message={error} /> : null}
      </section>

      <section className="grid gap-5">
        <Panel title="Generated draft">
          {generating ? (
            <LoadingState label="Calling qwen3.6-plus" rows={5} />
          ) : result ? (
            <div className="grid gap-4">
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
                  type="button"
                  onClick={() => void copyText("all", formatAll(result))}
                >
                  {copiedKey === "all" ? "Copied" : "Copy all"}
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
              {copyError ? <ErrorState title="Clipboard" message={copyError} /> : null}
            </div>
          ) : (
            <EmptyState title="No draft yet" description="Generate content from an analysis row or manual product input." />
          )}
        </Panel>
        <FallbackNotice
          source="sample"
          title="Draft for review"
          description="The generated copy should be reviewed against platform policies, claim evidence, and sample data limitations before publishing."
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
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="mt-3 whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-700">{section.text}</pre>
    </article>
  );
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
    evidenceFlag(score.evidence, "content_fallback_used", "Content evidence used fallback or sample data."),
    evidenceFlag(score.evidence, "competitor_fallback_used", "Competitor evidence used fallback or sample data."),
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
    { key: "title", title: "English title", text: result.title },
    { key: "bullets", title: "Five bullet points", text: result.bullet_points.map((item) => `- ${item}`).join("\n") },
    { key: "seo", title: "SEO keywords", text: result.seo_keywords.join(", ") },
    { key: "video", title: "Short video script", text: result.short_video_script },
    { key: "pinterest", title: "Pinterest image keywords", text: result.pinterest_keywords.join(", ") },
    { key: "listing", title: "Platform listing advice", text: result.platform_listing_advice },
    { key: "risk", title: "Risk notes", text: result.risk_notes.map((item) => `- ${item}`).join("\n") },
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
