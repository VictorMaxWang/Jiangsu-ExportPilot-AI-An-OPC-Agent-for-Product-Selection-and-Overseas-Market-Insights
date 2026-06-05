"use client";

import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/app/_components/ErrorState";
import { FallbackNotice } from "@/app/_components/FallbackNotice";
import { useI18n } from "@/app/_components/LanguageProvider";
import {
  Company,
  CompanyDraft,
  CompanyDraftUpdateRequest,
  CompanyIntakeEvidenceItem,
  CompanyIntakeEvidenceSource,
  confirmCompanyIntakeDraft,
  getFriendlyErrorMessage,
  rejectCompanyIntakeDraft,
  updateCompanyIntakeDraft,
} from "@/app/_lib/api-client";

type CompanyDraftEditorProps = {
  draft: CompanyDraft;
  onDraftChange?: (draft: CompanyDraft) => void;
  onConfirmed?: (company: Company) => void;
  onRejected?: (draft: CompanyDraft) => void;
};

type DraftFormState = {
  company_name: string;
  region: string;
  industry: string;
  description: string;
  main_products: string;
  target_countries: string;
  confidence_score: string;
  reject_reason: string;
};

type EvidenceRow = CompanyIntakeEvidenceItem & {
  key: string;
};

const EVIDENCE_SOURCES: CompanyIntakeEvidenceSource[] = [
  "photo_text",
  "photo_visual",
  "manual_text",
  "model_inference",
];

const EVIDENCE_SOURCE_LABELS: Record<CompanyIntakeEvidenceSource, { zh: string; en: string }> = {
  photo_text: { zh: "照片文本", en: "Photo text" },
  photo_visual: { zh: "照片视觉", en: "Photo visual" },
  manual_text: { zh: "手动文本", en: "Manual text" },
  model_inference: { zh: "模型推断", en: "Model inference" },
};

const IMAGE_ROLE_LABELS: Record<string, { zh: string; en: string }> = {
  business_card: { zh: "企业名片", en: "Business card" },
  catalog_cover: { zh: "目录封面", en: "Catalog cover" },
  brochure: { zh: "宣传册", en: "Brochure" },
  product_display: { zh: "产品展示", en: "Product display" },
  factory_photo: { zh: "工厂照片", en: "Factory photo" },
  business_license: { zh: "营业执照", en: "Business license" },
  other: { zh: "其他", en: "Other" },
  unknown: { zh: "未标注", en: "Unlabeled" },
};

export function CompanyDraftEditor({
  draft,
  onDraftChange,
  onConfirmed,
  onRejected,
}: CompanyDraftEditorProps) {
  const { text, locale } = useI18n();
  const [form, setForm] = useState<DraftFormState>(() => formFromDraft(draft));
  const [evidenceRows, setEvidenceRows] = useState<EvidenceRow[]>(() => evidenceRowsFromDraft(draft));
  const [action, setAction] = useState<"save" | "confirm" | "reject" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(formFromDraft(draft));
    setEvidenceRows(evidenceRowsFromDraft(draft));
    setNotice(null);
    setError(null);
  }, [draft]);

  const editable = draft.status === "draft";
  const busy = action !== null;
  const confidenceNumber = useMemo(() => toNumber(form.confidence_score), [form.confidence_score]);
  const lowConfidence = confidenceNumber === null || confidenceNumber < 0.65 || draft.low_confidence;

  async function handleSave() {
    setAction("save");
    setError(null);
    setNotice(null);
    try {
      const saved = await persistDraft();
      setNotice(text("企业草稿修改已保存。", "Company draft changes saved."));
      onDraftChange?.(saved);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function handleConfirm() {
    if (!form.company_name.trim()) {
      setError(text("确认入库前请填写企业名称。", "Enter the company name before confirming."));
      return;
    }

    setAction("confirm");
    setError(null);
    setNotice(null);
    try {
      const saved = await persistDraft();
      const company = await confirmCompanyIntakeDraft(saved.id);
      onDraftChange?.({ ...saved, status: "confirmed", confirmed_company_id: company.id });
      onConfirmed?.(company);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function handleReject() {
    const confirmed = window.confirm(
      text("确认拒绝该企业草稿？拒绝后不会创建正式企业。", "Reject this company draft? No company will be created."),
    );
    if (!confirmed) {
      return;
    }

    setAction("reject");
    setError(null);
    setNotice(null);
    try {
      const rejected = await rejectCompanyIntakeDraft(draft.id, { reason: optionalText(form.reject_reason) });
      setNotice(text("企业草稿已拒绝。", "Company draft rejected."));
      onDraftChange?.(rejected);
      onRejected?.(rejected);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function persistDraft(): Promise<CompanyDraft> {
    const payload = buildDraftUpdatePayload(form, evidenceRows);
    return updateCompanyIntakeDraft(draft.id, payload);
  }

  function updateEvidenceRow(key: string, patch: Partial<Omit<EvidenceRow, "key">>) {
    setEvidenceRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function addEvidenceRow() {
    setEvidenceRows((current) => [
      ...current,
      {
        key: `new-${Date.now()}-${current.length}`,
        field: "",
        source: "manual_text",
        value: "",
      },
    ]);
  }

  function removeEvidenceRow(key: string) {
    setEvidenceRows((current) => current.filter((row) => row.key !== key));
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">{text("企业草稿", "Company draft")}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {text(
              "识别结果需人工确认后才会入库，AI 提取不代表企业资质真实性验证。",
              "AI extraction must be reviewed before confirmation and does not verify company credentials.",
            )}
          </p>
        </div>
        <ConfidenceBadge value={form.confidence_score || draft.confidence_score} lowConfidence={lowConfidence} />
      </div>

      {lowConfidence ? (
        <div className="mt-4">
          <FallbackNotice
            source="ai"
            title={text("请逐项复核企业草稿", "Review this company draft field by field")}
            description={text(
              "企业名称、地区、行业、主营产品和目标市场建议可能不完整，确认入库前请人工核对。",
              "Company name, region, industry, products, and target-market suggestions may be incomplete. Review before confirmation.",
            )}
          />
        </div>
      ) : null}

      <div className="mt-5 grid gap-5">
        <DraftSection title={text("基础信息", "Basics")}>
          <div className="grid gap-4 md:grid-cols-2">
            <TextInput
              disabled={!editable}
              label={text("企业名称", "Company name")}
              required
              value={form.company_name}
              onChange={(value) => setForm({ ...form, company_name: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("地区", "Region")}
              value={form.region}
              onChange={(value) => setForm({ ...form, region: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("行业", "Industry")}
              value={form.industry}
              onChange={(value) => setForm({ ...form, industry: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("置信度", "Confidence")}
              value={form.confidence_score}
              onChange={(value) => setForm({ ...form, confidence_score: value })}
            />
          </div>
          <TextArea
            disabled={!editable}
            label={text("简介", "Description")}
            rows={4}
            value={form.description}
            onChange={(value) => setForm({ ...form, description: value })}
          />
        </DraftSection>

        <DraftSection title={text("主营产品与目标市场", "Products and target markets")}>
          <div className="grid gap-4 md:grid-cols-2">
            <TextArea
              disabled={!editable}
              label={text("主营产品", "Main products")}
              value={form.main_products}
              onChange={(value) => setForm({ ...form, main_products: value })}
            />
            <TextArea
              disabled={!editable}
              label={text("目标市场建议", "Target-market suggestions")}
              value={form.target_countries}
              onChange={(value) => setForm({ ...form, target_countries: value })}
            />
          </div>
        </DraftSection>

        <DraftSection title="evidence">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              {text("证据仅保留建档必要摘录和图片编号，不展示原始 OCR 全文。", "Evidence keeps only needed excerpts and image references, not full OCR text.")}
            </p>
            <button
              className="min-h-11 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={!editable}
              type="button"
              onClick={addEvidenceRow}
            >
              {text("添加证据", "Add evidence")}
            </button>
          </div>
          {evidenceRows.length === 0 ? (
            <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
              {text("暂无证据摘录，可人工添加字段、来源和简短摘录。", "No evidence excerpts yet. Add a field, source, and short excerpt manually.")}
            </p>
          ) : (
            <div className="grid gap-3">
              {evidenceRows.map((row) => (
                <div key={row.key} className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 lg:grid-cols-[1fr_1fr_2fr_auto]">
                  <div className="grid gap-2">
                    <EvidenceProvenance row={row} locale={locale} />
                    <TextInput
                      disabled={!editable}
                      label={text("字段", "Field")}
                      value={row.field}
                      onChange={(value) => updateEvidenceRow(row.key, { field: value })}
                    />
                  </div>
                  <label className="grid gap-2">
                    <span className="text-sm font-medium text-slate-700">{text("来源", "Source")}</span>
                    <select
                      className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
                      disabled={!editable}
                      value={row.source}
                      onChange={(event) => updateEvidenceRow(row.key, { source: event.target.value as CompanyIntakeEvidenceSource })}
                    >
                      {EVIDENCE_SOURCES.map((source) => (
                        <option key={source} value={source}>
                          {localizedLabel(EVIDENCE_SOURCE_LABELS[source], locale)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <TextInput
                    disabled={!editable}
                    label={text("摘录", "Excerpt")}
                    value={row.value ?? ""}
                    onChange={(value) => updateEvidenceRow(row.key, { value })}
                  />
                  <div className="flex items-end">
                    <button
                      className="min-h-11 rounded-md border border-red-200 px-3 py-2 text-sm font-medium text-red-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                      disabled={!editable}
                      type="button"
                      onClick={() => removeEvidenceRow(row.key)}
                    >
                      {text("删除", "Delete")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </DraftSection>

        <label className="grid gap-2">
          <span className="text-sm font-medium text-slate-700">{text("拒绝原因（可选）", "Reject reason (optional)")}</span>
          <input
            className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={!editable}
            value={form.reject_reason}
            onChange={(event) => setForm({ ...form, reject_reason: event.target.value })}
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            className="min-h-11 rounded-md border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={!editable || busy}
            type="button"
            onClick={() => void handleSave()}
          >
            {action === "save" ? text("保存中", "Saving") : text("保存修改", "Save changes")}
          </button>
          <button
            className="min-h-11 rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!editable || busy || !form.company_name.trim()}
            type="button"
            onClick={() => void handleConfirm()}
          >
            {action === "confirm" ? text("入库中", "Confirming") : text("确认入库", "Confirm company")}
          </button>
          <button
            className="min-h-11 rounded-md border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            disabled={!editable || busy}
            type="button"
            onClick={() => void handleReject()}
          >
            {action === "reject" ? text("拒绝中", "Rejecting") : text("拒绝草稿", "Reject draft")}
          </button>
        </div>

        {notice ? <p className="rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
        {error ? <ErrorState message={error} /> : null}
        {!editable ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            {text(`当前草稿状态为 ${draft.status}，不可继续编辑。`, `Current draft status is ${draft.status}; editing is disabled.`)}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function DraftSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-4">
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {children}
    </section>
  );
}

function TextInput({
  label,
  value,
  onChange,
  disabled = false,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  required?: boolean;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
        disabled={disabled}
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
  disabled = false,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  rows?: number;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <textarea
        className="min-h-24 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
        disabled={disabled}
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ConfidenceBadge({ value, lowConfidence = false }: { value: string | number | null; lowConfidence?: boolean }) {
  const { text } = useI18n();
  const score = toNumber(value);
  const percentage = score === null ? text("待补充", "Missing") : `${Math.round(score * 100)}%`;
  const level = score === null || score < 0.35 ? "manual" : score < 0.65 || lowConfidence ? "low" : "high";

  const className = {
    high: "bg-jade/10 text-jade ring-jade/20",
    low: "bg-wheat/15 text-ink ring-wheat/30",
    manual: "bg-red-50 text-red-700 ring-red-200",
  }[level];

  const label = {
    high: text("AI 置信度较高", "Higher AI confidence"),
    low: text("AI 置信度偏低", "Lower AI confidence"),
    manual: text("需要人工补全", "Manual completion needed"),
  }[level];

  return (
    <span className={`inline-flex w-fit items-center rounded-md px-2.5 py-1 text-xs font-semibold ring-1 ${className}`}>
      {label} · {percentage}
    </span>
  );
}

function EvidenceProvenance({ row, locale }: { row: EvidenceRow; locale: "zh-CN" | "en" }) {
  const imageIndex = typeof row.image_index === "number" ? row.image_index : null;
  if (imageIndex === null && !row.image_role) {
    return null;
  }
  const imageLabel =
    imageIndex === null
      ? localizedPlain({ zh: "图片未标号", en: "Image not numbered" }, locale)
      : `${localizedPlain({ zh: "图片", en: "Image" }, locale)} #${imageIndex + 1}`;
  const roleLabel = row.image_role
    ? localizedLabel(IMAGE_ROLE_LABELS[row.image_role] ?? { zh: row.image_role, en: row.image_role }, locale)
    : null;
  return (
    <p className="w-fit rounded-md border border-river/20 bg-river/5 px-2 py-1 text-xs font-semibold text-river">
      {roleLabel ? `${imageLabel} · ${roleLabel}` : imageLabel}
    </p>
  );
}

function formFromDraft(draft: CompanyDraft): DraftFormState {
  return {
    company_name: draft.company_name ?? "",
    region: draft.region ?? "",
    industry: draft.industry ?? "",
    description: draft.description ?? "",
    main_products: listToText(draft.main_products),
    target_countries: listToText(draft.target_countries),
    confidence_score: draft.confidence_score ?? "",
    reject_reason: "",
  };
}

function evidenceRowsFromDraft(draft: CompanyDraft): EvidenceRow[] {
  return (draft.evidence ?? []).map((item, index) => ({
    key: `${draft.id}-${index}`,
    field: item.field,
    source: item.source,
    image_index: item.image_index,
    image_role: item.image_role,
    value: item.value ?? "",
  }));
}

function buildDraftUpdatePayload(form: DraftFormState, evidenceRows: EvidenceRow[]): CompanyDraftUpdateRequest {
  return {
    company_name: optionalText(form.company_name),
    region: optionalText(form.region),
    industry: optionalText(form.industry),
    description: optionalText(form.description),
    main_products: textToList(form.main_products),
    target_countries: textToCountryCodes(form.target_countries),
    confidence_score: optionalText(form.confidence_score),
    evidence: buildEvidencePayload(evidenceRows),
  };
}

function buildEvidencePayload(evidenceRows: EvidenceRow[]): CompanyIntakeEvidenceItem[] {
  return evidenceRows
    .map((row) => {
      const item: CompanyIntakeEvidenceItem = {
        field: row.field.trim(),
        source: row.source,
        value: optionalText(row.value ?? ""),
      };
      if (typeof row.image_index === "number") {
        item.image_index = row.image_index;
      }
      if (row.image_role) {
        item.image_role = row.image_role;
      }
      return item;
    })
    .filter((row) => row.field);
}

function listToText(values?: string[] | null): string {
  return (values ?? []).join("\n");
}

function textToList(value: string): string[] {
  const seen = new Set<string>();
  return value
    .split(/\r?\n|[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase();
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
}

function textToCountryCodes(value: string): string[] {
  return textToList(value)
    .map((item) => item.replace(/[^A-Za-z]/g, "").toUpperCase())
    .filter((item) => item.length === 2);
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function toNumber(value: string | number | null): number | null {
  if (value === null || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function localizedLabel(label: { zh: string; en: string }, locale: "zh-CN" | "en"): string {
  return locale === "en" ? label.en : label.zh;
}

function localizedPlain(label: { zh: string; en: string }, locale: "zh-CN" | "en"): string {
  return locale === "en" ? label.en : label.zh;
}
