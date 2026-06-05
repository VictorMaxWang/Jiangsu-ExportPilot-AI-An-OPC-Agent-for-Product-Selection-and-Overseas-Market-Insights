"use client";

import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/app/_components/ErrorState";
import { FallbackNotice } from "@/app/_components/FallbackNotice";
import { useI18n } from "@/app/_components/LanguageProvider";
import {
  Product,
  ProductDraft,
  ProductDraftUpdateRequest,
  ProductIntakeEvidenceItem,
  ProductIntakeEvidenceSource,
  confirmProductIntakeDraft,
  getFriendlyErrorMessage,
  rejectProductIntakeDraft,
  updateProductIntakeDraft,
} from "@/app/_lib/api-client";
import { ConfidenceBadge } from "./ConfidenceBadge";

type ProductDraftEditorProps = {
  draft: ProductDraft;
  onDraftChange?: (draft: ProductDraft) => void;
  onConfirmed?: (product: Product) => void;
  onRejected?: (draft: ProductDraft) => void;
};

type DraftFormState = {
  product_name_cn: string;
  product_name_en: string;
  category: string;
  price_cny: string;
  cost_price_cny: string;
  weight_kg: string;
  material: string;
  package_size: string;
  color_options: string;
  specification: string;
  selling_points_cn: string;
  selling_points_en: string;
  usage_scenarios: string;
  target_users: string;
  cross_border_keywords_en: string;
  risk_notes: string;
  confidence_score: string;
  reject_reason: string;
};

type EvidenceRow = ProductIntakeEvidenceItem & {
  key: string;
};

const EVIDENCE_SOURCES: ProductIntakeEvidenceSource[] = [
  "screenshot_text",
  "screenshot_visual",
  "url_text",
  "manual_text",
  "model_inference",
];

const EVIDENCE_SOURCE_LABELS: Record<ProductIntakeEvidenceSource, { zh: string; en: string }> = {
  screenshot_text: { zh: "截图文本", en: "Screenshot text" },
  screenshot_visual: { zh: "截图视觉", en: "Screenshot visual" },
  url_text: { zh: "链接文本", en: "URL text" },
  manual_text: { zh: "手动文本", en: "Manual text" },
  model_inference: { zh: "模型推断", en: "Model inference" },
};

const IMAGE_ROLE_LABELS: Record<string, { zh: string; en: string }> = {
  main: { zh: "主图", en: "Main image" },
  primary: { zh: "主图", en: "Main image" },
  cover: { zh: "主图", en: "Main image" },
  hero: { zh: "主图", en: "Main image" },
  spec: { zh: "规格图", en: "Specification" },
  detail: { zh: "详情图", en: "Detail" },
  package: { zh: "包装图", en: "Packaging" },
  other: { zh: "其他", en: "Other" },
  unknown: { zh: "未标注", en: "Unlabeled" },
  screenshot: { zh: "截图", en: "Screenshot" },
};

export function ProductDraftEditor({
  draft,
  onDraftChange,
  onConfirmed,
  onRejected,
}: ProductDraftEditorProps) {
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
      setNotice(text("草稿修改已保存。", "Draft changes saved."));
      onDraftChange?.(saved);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function handleConfirm() {
    if (!form.product_name_cn.trim()) {
      setError(text("确认入库前请填写商品中文名。", "Enter the Chinese product name before confirming."));
      return;
    }

    setAction("confirm");
    setError(null);
    setNotice(null);
    try {
      const saved = await persistDraft();
      const product = await confirmProductIntakeDraft(saved.id, { company_id: saved.company_id });
      onDraftChange?.({ ...saved, status: "confirmed", confirmed_product_id: product.id });
      onConfirmed?.(product);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function handleReject() {
    const confirmed = window.confirm(
      text("确认拒绝该草稿？拒绝后不会创建正式产品。", "Reject this draft? No product will be created."),
    );
    if (!confirmed) {
      return;
    }

    setAction("reject");
    setError(null);
    setNotice(null);
    try {
      const rejected = await rejectProductIntakeDraft(draft.id, {
        company_id: draft.company_id,
        reason: optionalText(form.reject_reason),
      });
      setNotice(text("草稿已拒绝。", "Draft rejected."));
      onDraftChange?.(rejected);
      onRejected?.(rejected);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function persistDraft(): Promise<ProductDraft> {
    const payload = buildDraftUpdatePayload(form, evidenceRows, draft);
    return updateProductIntakeDraft(draft.id, payload);
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
        source: "model_inference",
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
          <h2 className="text-lg font-semibold text-ink">{text("草稿编辑", "Draft editor")}</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {text(
              "识别结果需人工确认后才会入库，参考价格不代表成交价或采购成本。",
              "AI extraction must be reviewed before confirmation. Reference prices are not transaction or sourcing costs.",
            )}
          </p>
        </div>
        <ConfidenceBadge value={form.confidence_score || draft.confidence_score} lowConfidence={lowConfidence} />
      </div>

      {lowConfidence ? (
        <div className="mt-4">
          <FallbackNotice
            source="ai"
            title={text("请逐项复核低置信度草稿", "Review this low-confidence draft field by field")}
            description={text(
              "产品名、价格、规格、材质、卖点和证据可能不完整，确认入库前请人工核对。",
              "Name, price, specs, material, selling points, and evidence may be incomplete. Review before confirmation.",
            )}
          />
        </div>
      ) : null}

      <div className="mt-5 grid gap-5">
        <DraftSection title={text("基础字段", "Basics")}>
          <div className="grid gap-4 md:grid-cols-2">
            <TextInput
              disabled={!editable}
              label={text("商品中文名", "Chinese product name")}
              required
              value={form.product_name_cn}
              onChange={(value) => setForm({ ...form, product_name_cn: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("英文名", "English name")}
              value={form.product_name_en}
              onChange={(value) => setForm({ ...form, product_name_en: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("类目", "Category")}
              value={form.category}
              onChange={(value) => setForm({ ...form, category: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("参考价格 CNY", "Reference price CNY")}
              value={form.price_cny}
              onChange={(value) => setForm({ ...form, price_cny: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("确认采购成本 CNY", "Confirmed cost CNY")}
              value={form.cost_price_cny}
              onChange={(value) => setForm({ ...form, cost_price_cny: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("置信度", "Confidence")}
              value={form.confidence_score}
              onChange={(value) => setForm({ ...form, confidence_score: value })}
            />
          </div>
        </DraftSection>

        <DraftSection title={text("产品属性", "Product attributes")}>
          <div className="grid gap-4 md:grid-cols-2">
            <TextInput
              disabled={!editable}
              label={text("材质", "Material")}
              value={form.material}
              onChange={(value) => setForm({ ...form, material: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("包装尺寸", "Package size")}
              value={form.package_size}
              onChange={(value) => setForm({ ...form, package_size: value })}
            />
            <TextInput
              disabled={!editable}
              label={text("重量 kg", "Weight kg")}
              value={form.weight_kg}
              onChange={(value) => setForm({ ...form, weight_kg: value })}
            />
            <TextArea
              disabled={!editable}
              label={text("颜色选项", "Color options")}
              rows={3}
              value={form.color_options}
              onChange={(value) => setForm({ ...form, color_options: value })}
            />
          </div>
          <TextArea
            disabled={!editable}
            label={text("规格", "Specification")}
            rows={4}
            value={form.specification}
            onChange={(value) => setForm({ ...form, specification: value })}
          />
        </DraftSection>

        <DraftSection title={text("卖点与使用场景", "Selling points and use")}>
          <div className="grid gap-4 md:grid-cols-2">
            <TextArea
              disabled={!editable}
              label={text("中文卖点", "Chinese selling points")}
              value={form.selling_points_cn}
              onChange={(value) => setForm({ ...form, selling_points_cn: value })}
            />
            <TextArea
              disabled={!editable}
              label={text("英文卖点", "English selling points")}
              value={form.selling_points_en}
              onChange={(value) => setForm({ ...form, selling_points_en: value })}
            />
            <TextArea
              disabled={!editable}
              label={text("使用场景", "Usage scenarios")}
              value={form.usage_scenarios}
              onChange={(value) => setForm({ ...form, usage_scenarios: value })}
            />
            <TextArea
              disabled={!editable}
              label={text("目标人群", "Target users")}
              value={form.target_users}
              onChange={(value) => setForm({ ...form, target_users: value })}
            />
          </div>
          <TextArea
            disabled={!editable}
            label={text("英文跨境关键词", "English cross-border keywords")}
            value={form.cross_border_keywords_en}
            onChange={(value) => setForm({ ...form, cross_border_keywords_en: value })}
          />
        </DraftSection>

        <DraftSection title={text("证据与风险", "Evidence and risks")}>
          <TextArea
            disabled={!editable}
            label={text("风险提示", "Risk notes")}
            value={form.risk_notes}
            onChange={(value) => setForm({ ...form, risk_notes: value })}
          />

          <div className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-ink">evidence</h3>
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
                {text(
                  "暂无证据摘录，可人工添加字段、来源和简短摘录。",
                  "No evidence excerpts yet. Add a field, source, and short excerpt manually.",
                )}
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
                        onChange={(event) => updateEvidenceRow(row.key, { source: event.target.value as ProductIntakeEvidenceSource })}
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
          </div>
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
            disabled={!editable || busy || !form.product_name_cn.trim()}
            type="button"
            onClick={() => void handleConfirm()}
          >
            {action === "confirm" ? text("入库中", "Confirming") : text("确认入库", "Confirm product")}
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

function EvidenceProvenance({ row, locale }: { row: EvidenceRow; locale: "zh-CN" | "en" }) {
  const imageIndex = typeof row.image_index === "number" ? row.image_index : null;
  if (imageIndex === null && !row.image_role) {
    return null;
  }
  const imageLabel = imageIndex === null ? localizedPlain({ zh: "图片未标号", en: "Image not numbered" }, locale) : `${localizedPlain({ zh: "图片", en: "Image" }, locale)} #${imageIndex + 1}`;
  const roleLabel = row.image_role ? localizedLabel(IMAGE_ROLE_LABELS[row.image_role] ?? { zh: row.image_role, en: row.image_role }, locale) : null;
  return (
    <p className="w-fit rounded-md border border-river/20 bg-river/5 px-2 py-1 text-xs font-semibold text-river">
      {roleLabel ? `${imageLabel} · ${roleLabel}` : imageLabel}
    </p>
  );
}

function formFromDraft(draft: ProductDraft): DraftFormState {
  const sellingPoints = draft.selling_points ?? {};
  return {
    product_name_cn: draft.product_name_cn ?? "",
    product_name_en: draft.product_name_en ?? "",
    category: draft.category ?? "",
    price_cny: draft.price_cny ?? "",
    cost_price_cny: draft.cost_price_cny ?? "",
    weight_kg: draft.weight_kg ?? "",
    material: draft.material ?? "",
    package_size: draft.package_size ?? "",
    color_options: listToText(draft.color_options),
    specification: draft.specification ?? "",
    selling_points_cn: listToText(sellingPoints.selling_points_cn),
    selling_points_en: listToText(sellingPoints.selling_points_en),
    usage_scenarios: listToText(sellingPoints.usage_scenarios),
    target_users: listToText(draft.target_users),
    cross_border_keywords_en: listToText(sellingPoints.cross_border_keywords_en),
    risk_notes: listToText(sellingPoints.risk_notes),
    confidence_score: draft.confidence_score ?? "",
    reject_reason: "",
  };
}

function evidenceRowsFromDraft(draft: ProductDraft): EvidenceRow[] {
  return (draft.evidence ?? []).map((item, index) => ({
    key: `${draft.id}-${index}`,
    field: item.field,
    source: item.source,
    image_index: item.image_index,
    image_role: item.image_role,
    value: item.value ?? "",
  }));
}

function buildDraftUpdatePayload(
  form: DraftFormState,
  evidenceRows: EvidenceRow[],
  draft: ProductDraft,
): ProductDraftUpdateRequest {
  const sellingPoints = draft.selling_points ?? {};
  const riskNotes = textToList(form.risk_notes);
  return {
    product_name_cn: optionalText(form.product_name_cn),
    product_name_en: optionalText(form.product_name_en),
    category: optionalText(form.category),
    price_cny: optionalText(form.price_cny),
    cost_price_cny: optionalText(form.cost_price_cny),
    weight_kg: optionalText(form.weight_kg),
    package_size: optionalText(form.package_size),
    material: optionalText(form.material),
    color_options: textToList(form.color_options),
    specification: optionalText(form.specification),
    selling_points: {
      selling_points_cn: textToList(form.selling_points_cn),
      selling_points_en: textToList(form.selling_points_en),
      usage_scenarios: textToList(form.usage_scenarios),
      cross_border_keywords_en: textToList(form.cross_border_keywords_en),
      risk_notes: riskNotes,
    },
    target_users: textToList(form.target_users),
    risk_notes: riskNotes,
    confidence_score: optionalText(form.confidence_score),
    evidence: buildEvidencePayload(evidenceRows),
  };
}

function buildEvidencePayload(evidenceRows: EvidenceRow[]): ProductIntakeEvidenceItem[] {
  return evidenceRows
    .map((row) => {
      const item: ProductIntakeEvidenceItem = {
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
    .split(/\r?\n|[,，]/)
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

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function toNumber(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function localizedLabel(label: { zh: string; en: string }, locale: "zh-CN" | "en"): string {
  return locale === "en" ? label.en : label.zh;
}

function localizedPlain(label: { zh: string; en: string }, locale: "zh-CN" | "en"): string {
  return locale === "en" ? label.en : label.zh;
}
