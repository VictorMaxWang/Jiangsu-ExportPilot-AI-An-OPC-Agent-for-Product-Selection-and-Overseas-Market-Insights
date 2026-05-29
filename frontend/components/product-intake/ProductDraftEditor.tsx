"use client";

import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/app/_components/ErrorState";
import { FallbackNotice } from "@/app/_components/FallbackNotice";
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
  material: string;
  specification: string;
  package_size: string;
  selling_points_cn: string;
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

export function ProductDraftEditor({
  draft,
  onDraftChange,
  onConfirmed,
  onRejected,
}: ProductDraftEditorProps) {
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
      setNotice("草稿修改已保存。");
      onDraftChange?.(saved);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setAction(null);
    }
  }

  async function handleConfirm() {
    if (!form.product_name_cn.trim()) {
      setError("确认入库前请填写商品中文名。");
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
    const confirmed = window.confirm("确认拒绝该草稿？拒绝后不会创建正式产品。");
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
      setNotice("草稿已拒绝。");
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
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">草稿编辑</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            识别结果需人工确认后才会入库，参考价格不代表成交价或采购成本。
          </p>
        </div>
        <ConfidenceBadge value={form.confidence_score || draft.confidence_score} lowConfidence={lowConfidence} />
      </div>

      {lowConfidence ? (
        <div className="mt-4">
          <FallbackNotice
            source="ai"
            title="请逐项复核低置信度草稿"
            description="产品名、价格、规格、材质、卖点和证据可能不完整，确认入库前请人工核对。"
          />
        </div>
      ) : null}

      <div className="mt-5 grid gap-4">
        <div className="grid gap-4 md:grid-cols-2">
          <TextInput
            disabled={!editable}
            label="商品中文名"
            required
            value={form.product_name_cn}
            onChange={(value) => setForm({ ...form, product_name_cn: value })}
          />
          <TextInput
            disabled={!editable}
            label="英文名"
            value={form.product_name_en}
            onChange={(value) => setForm({ ...form, product_name_en: value })}
          />
          <TextInput
            disabled={!editable}
            label="类目"
            value={form.category}
            onChange={(value) => setForm({ ...form, category: value })}
          />
          <TextInput
            disabled={!editable}
            label="价格 CNY"
            value={form.price_cny}
            onChange={(value) => setForm({ ...form, price_cny: value })}
          />
          <TextInput
            disabled={!editable}
            label="材质"
            value={form.material}
            onChange={(value) => setForm({ ...form, material: value })}
          />
          <TextInput
            disabled={!editable}
            label="尺寸/包装"
            value={form.package_size}
            onChange={(value) => setForm({ ...form, package_size: value })}
          />
        </div>

        <TextArea
          disabled={!editable}
          label="规格"
          rows={3}
          value={form.specification}
          onChange={(value) => setForm({ ...form, specification: value })}
        />
        <TextArea
          disabled={!editable}
          label="卖点"
          value={form.selling_points_cn}
          onChange={(value) => setForm({ ...form, selling_points_cn: value })}
        />
        <div className="grid gap-4 md:grid-cols-2">
          <TextArea
            disabled={!editable}
            label="目标人群"
            value={form.target_users}
            onChange={(value) => setForm({ ...form, target_users: value })}
          />
          <TextArea
            disabled={!editable}
            label="英文关键词"
            value={form.cross_border_keywords_en}
            onChange={(value) => setForm({ ...form, cross_border_keywords_en: value })}
          />
        </div>
        <TextArea
          disabled={!editable}
          label="风险提示"
          value={form.risk_notes}
          onChange={(value) => setForm({ ...form, risk_notes: value })}
        />
        <TextInput
          disabled={!editable}
          label="置信度"
          value={form.confidence_score}
          onChange={(value) => setForm({ ...form, confidence_score: value })}
        />

        <div className="grid gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-ink">evidence</h3>
            <button
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={!editable}
              type="button"
              onClick={addEvidenceRow}
            >
              添加证据
            </button>
          </div>
          {evidenceRows.length === 0 ? (
            <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
              暂无证据摘录，可人工添加字段、来源和简短摘录。
            </p>
          ) : (
            <div className="grid gap-3">
              {evidenceRows.map((row) => (
                <div key={row.key} className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 md:grid-cols-[1fr_1fr_2fr_auto]">
                  <TextInput
                    disabled={!editable}
                    label="字段"
                    value={row.field}
                    onChange={(value) => updateEvidenceRow(row.key, { field: value })}
                  />
                  <label className="grid gap-2">
                    <span className="text-sm font-medium text-slate-700">来源</span>
                    <select
                      className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
                      disabled={!editable}
                      value={row.source}
                      onChange={(event) => updateEvidenceRow(row.key, { source: event.target.value as ProductIntakeEvidenceSource })}
                    >
                      {EVIDENCE_SOURCES.map((source) => (
                        <option key={source} value={source}>
                          {source}
                        </option>
                      ))}
                    </select>
                  </label>
                  <TextInput
                    disabled={!editable}
                    label="摘录"
                    value={row.value ?? ""}
                    onChange={(value) => updateEvidenceRow(row.key, { value })}
                  />
                  <div className="flex items-end">
                    <button
                      className="rounded-md border border-red-200 px-3 py-2 text-sm font-medium text-red-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                      disabled={!editable}
                      type="button"
                      onClick={() => removeEvidenceRow(row.key)}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <label className="grid gap-2">
          <span className="text-sm font-medium text-slate-700">拒绝原因（可选）</span>
          <input
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={!editable}
            value={form.reject_reason}
            onChange={(event) => setForm({ ...form, reject_reason: event.target.value })}
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-md border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
            disabled={!editable || busy}
            type="button"
            onClick={() => void handleSave()}
          >
            {action === "save" ? "保存中" : "保存修改"}
          </button>
          <button
            className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!editable || busy || !form.product_name_cn.trim()}
            type="button"
            onClick={() => void handleConfirm()}
          >
            {action === "confirm" ? "入库中" : "确认入库"}
          </button>
          <button
            className="rounded-md border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            disabled={!editable || busy}
            type="button"
            onClick={() => void handleReject()}
          >
            {action === "reject" ? "拒绝中" : "拒绝草稿"}
          </button>
        </div>

        {notice ? <p className="rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
        {error ? <ErrorState message={error} /> : null}
        {!editable ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            当前草稿状态为 {draft.status}，不可继续编辑。
          </p>
        ) : null}
      </div>
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
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
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

function formFromDraft(draft: ProductDraft): DraftFormState {
  const sellingPoints = draft.selling_points ?? {};
  return {
    product_name_cn: draft.product_name_cn ?? "",
    product_name_en: draft.product_name_en ?? "",
    category: draft.category ?? "",
    price_cny: draft.price_cny ?? "",
    material: draft.material ?? "",
    specification: draft.specification ?? "",
    package_size: draft.package_size ?? "",
    selling_points_cn: listToText(sellingPoints.selling_points_cn),
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
    material: optionalText(form.material),
    specification: optionalText(form.specification),
    package_size: optionalText(form.package_size),
    selling_points: {
      selling_points_cn: textToList(form.selling_points_cn),
      selling_points_en: sellingPoints.selling_points_en ?? [],
      usage_scenarios: sellingPoints.usage_scenarios ?? [],
      cross_border_keywords_en: textToList(form.cross_border_keywords_en),
      risk_notes: riskNotes,
    },
    target_users: textToList(form.target_users),
    risk_notes: riskNotes,
    confidence_score: optionalText(form.confidence_score),
    evidence: evidenceRows
      .map((row) => ({
        field: row.field.trim(),
        source: row.source,
        value: optionalText(row.value ?? ""),
      }))
      .filter((row) => row.field),
  };
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
