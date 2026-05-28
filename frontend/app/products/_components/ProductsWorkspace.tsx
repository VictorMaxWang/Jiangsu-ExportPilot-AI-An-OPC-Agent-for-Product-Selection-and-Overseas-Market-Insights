"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { EmptyState } from "../../_components/EmptyState";
import { ErrorState } from "../../_components/ErrorState";
import { FallbackNotice } from "../../_components/FallbackNotice";
import { LoadingState } from "../../_components/LoadingState";
import {
  Company,
  CsvImportMode,
  CsvImportResult,
  Product,
  ProductKeywordGenerationResponse,
  ProductPayload,
  createProduct,
  deleteProduct,
  generateProductKeywords,
  getCsvImportResultFromError,
  getFriendlyErrorMessage,
  importProductSample,
  importProductUpload,
  listCompanies,
  listProducts,
  updateProduct,
} from "../../_lib/api-client";

type ProductFormState = {
  company_id: string;
  product_name_cn: string;
  product_name_en: string;
  category: string;
  cost_price_cny: string;
  weight_kg: string;
  package_size: string;
  material: string;
  certification: string;
  moq: string;
  description: string;
};

type KeywordState = {
  target_country: string;
  target_platforms: string;
};

const emptyProductForm: ProductFormState = {
  company_id: "",
  product_name_cn: "",
  product_name_en: "",
  category: "",
  cost_price_cny: "",
  weight_kg: "",
  package_size: "",
  material: "",
  certification: "",
  moq: "",
  description: "",
};

export function ProductsWorkspace() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProductFormState>(emptyProductForm);
  const [keywordForm, setKeywordForm] = useState<KeywordState>({ target_country: "JP", target_platforms: "Amazon, Rakuten" });
  const [keywordResult, setKeywordResult] = useState<ProductKeywordGenerationResponse | null>(null);
  const [importResult, setImportResult] = useState<CsvImportResult | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedProduct = useMemo(
    () => products.find((product) => product.id === selectedProductId) ?? null,
    [products, selectedProductId],
  );

  useEffect(() => {
    void loadInitialData();
  }, []);

  async function loadInitialData() {
    setLoading(true);
    setError(null);
    try {
      const [companyResponse, productResponse] = await Promise.all([listCompanies(), listProducts()]);
      setCompanies(companyResponse.items);
      setProducts(productResponse.items);
      const firstCompanyId = companyResponse.items[0]?.id ?? null;
      setSelectedCompanyId((current) => current ?? firstCompanyId);
      setForm((current) => ({
        ...current,
        company_id: current.company_id || (firstCompanyId ? String(firstCompanyId) : ""),
      }));
      setSelectedProductId((current) => {
        if (current && productResponse.items.some((product) => product.id === current)) {
          return current;
        }
        return productResponse.items[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function refreshProducts(companyId: number | null = selectedCompanyId) {
    setError(null);
    try {
      const response = await listProducts(companyId ?? undefined);
      setProducts(response.items);
      setSelectedProductId((current) => {
        if (current && response.items.some((product) => product.id === current)) {
          return current;
        }
        return response.items[0]?.id ?? null;
      });
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    }
  }

  function handleCompanyFilter(companyId: number | null) {
    setSelectedCompanyId(companyId);
    setImportResult(null);
    setForm((current) => ({
      ...current,
      company_id: companyId ? String(companyId) : current.company_id,
    }));
    void refreshProducts(companyId);
  }

  function startCreate() {
    setEditingId(null);
    setKeywordResult(null);
    setForm({
      ...emptyProductForm,
      company_id: selectedCompanyId ? String(selectedCompanyId) : companies[0] ? String(companies[0].id) : "",
    });
  }

  function startEdit(product: Product) {
    setEditingId(product.id);
    setSelectedProductId(product.id);
    setKeywordResult(null);
    setForm({
      company_id: String(product.company_id),
      product_name_cn: product.product_name_cn,
      product_name_en: product.product_name_en ?? "",
      category: product.category ?? "",
      cost_price_cny: product.cost_price_cny ?? "",
      weight_kg: product.weight_kg ?? "",
      package_size: product.package_size ?? "",
      material: product.material ?? "",
      certification: product.certification ?? "",
      moq: product.moq === null ? "" : String(product.moq),
      description: product.description ?? "",
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const payload = toProductPayload(form);
      const saved = editingId ? await updateProduct(editingId, payload) : await createProduct(payload);
      setProducts((current) => {
        if (editingId) {
          return current.map((product) => (product.id === saved.id ? saved : product));
        }
        return [saved, ...current];
      });
      setSelectedProductId(saved.id);
      setEditingId(null);
      setForm({ ...emptyProductForm, company_id: String(saved.company_id) });
      setNotice(editingId ? "产品信息已更新。" : "产品已创建。");
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(product: Product) {
    const confirmed = window.confirm(`确认删除产品“${product.product_name_cn}”？`);
    if (!confirmed) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await deleteProduct(product.id);
      setProducts((current) => current.filter((item) => item.id !== product.id));
      setSelectedProductId((current) => (current === product.id ? null : current));
      if (editingId === product.id) {
        startCreate();
      }
      setNotice("产品已删除。");
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  async function runSampleImport(mode: CsvImportMode) {
    if (!selectedCompanyId) {
      setError("请先选择企业后再导入产品。");
      return;
    }
    await runImport(() => importProductSample(selectedCompanyId, mode), mode);
  }

  async function runUploadImport(mode: CsvImportMode) {
    if (!selectedCompanyId) {
      setError("请先选择企业后再导入产品。");
      return;
    }
    if (!uploadFile) {
      setError("请先选择 CSV 文件。");
      return;
    }
    await runImport(() => importProductUpload(selectedCompanyId, mode, uploadFile), mode);
  }

  async function runImport(action: () => Promise<CsvImportResult>, mode: CsvImportMode) {
    setImporting(true);
    setError(null);
    setNotice(null);
    setImportResult(null);
    try {
      const result = await action();
      setImportResult(result);
      if (mode === "insert") {
        await refreshProducts(selectedCompanyId);
      }
      setNotice(mode === "validate" ? "CSV 校验通过。" : "产品 CSV 已导入。");
    } catch (requestError) {
      const csvResult = getCsvImportResultFromError(requestError);
      if (csvResult) {
        setImportResult(csvResult);
      }
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setImporting(false);
    }
  }

  async function handleGenerateKeywords() {
    if (!selectedProduct) {
      setError("请先选择产品。");
      return;
    }
    setGenerating(true);
    setError(null);
    setNotice(null);
    try {
      const result = await generateProductKeywords(selectedProduct.id, {
        target_country: optionalText(keywordForm.target_country),
        target_platforms: splitList(keywordForm.target_platforms) ?? [],
        persist: true,
      });
      setKeywordResult(result);
      setProducts((current) =>
        current.map((product) =>
          product.id === selectedProduct.id ? { ...product, product_name_en: result.product_name_en } : product,
        ),
      );
      setNotice(`关键词已生成，新增保存 ${result.saved_keywords_count} 个关键词。`);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="grid gap-5">
        <Panel title={editingId ? "编辑产品" : "新增产品"}>
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">所属企业</span>
              <select
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                required
                value={form.company_id}
                onChange={(event) => setForm({ ...form, company_id: event.target.value })}
              >
                <option value="">选择企业</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>
            <TextInput label="中文产品名" required value={form.product_name_cn} onChange={(value) => setForm({ ...form, product_name_cn: value })} />
            <TextInput label="英文产品名" value={form.product_name_en} onChange={(value) => setForm({ ...form, product_name_en: value })} />
            <TextInput label="品类" value={form.category} onChange={(value) => setForm({ ...form, category: value })} />
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput label="成本价 CNY" value={form.cost_price_cny} onChange={(value) => setForm({ ...form, cost_price_cny: value })} />
              <TextInput label="重量 kg" value={form.weight_kg} onChange={(value) => setForm({ ...form, weight_kg: value })} />
              <TextInput label="包装尺寸" value={form.package_size} onChange={(value) => setForm({ ...form, package_size: value })} />
              <TextInput label="MOQ" value={form.moq} onChange={(value) => setForm({ ...form, moq: value })} />
            </div>
            <TextInput label="材质" value={form.material} onChange={(value) => setForm({ ...form, material: value })} />
            <TextInput label="认证" value={form.certification} onChange={(value) => setForm({ ...form, certification: value })} />
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">产品描述</span>
              <textarea
                className="min-h-24 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                className="rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={submitting || !form.company_id || !form.product_name_cn.trim()}
                type="submit"
              >
                {submitting ? "保存中" : editingId ? "保存修改" : "创建产品"}
              </button>
              {editingId ? (
                <button className="rounded-md border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700" onClick={startCreate} type="button">
                  新增
                </button>
              ) : null}
            </div>
          </form>
        </Panel>

        <Panel title="CSV 导入">
          <div className="grid gap-4">
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">导入企业</span>
              <select
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                value={selectedCompanyId ?? ""}
                onChange={(event) => handleCompanyFilter(event.target.value ? Number(event.target.value) : null)}
              >
                <option value="">选择企业</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <button className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100" disabled={!selectedCompanyId || importing} onClick={() => void runSampleImport("validate")} type="button">
                校验样本 CSV
              </button>
              <button className="rounded-md bg-river px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300" disabled={!selectedCompanyId || importing} onClick={() => void runSampleImport("insert")} type="button">
                导入样本 CSV
              </button>
            </div>
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">上传 CSV</span>
              <input
                accept=".csv,text/csv"
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                type="file"
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100" disabled={!selectedCompanyId || !uploadFile || importing} onClick={() => void runUploadImport("validate")} type="button">
                校验上传 CSV
              </button>
              <button className="rounded-md bg-river px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300" disabled={!selectedCompanyId || !uploadFile || importing} onClick={() => void runUploadImport("insert")} type="button">
                导入上传 CSV
              </button>
            </div>
            {!selectedCompanyId ? <FallbackNotice source="csv" title="请先选择企业" description="产品 CSV 不包含 company_id，导入前需要指定归属企业。" /> : null}
            {importResult ? <ImportResult result={importResult} /> : null}
          </div>
        </Panel>
      </section>

      <section className="grid gap-5">
        <Panel title="产品列表">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <select
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
              value={selectedCompanyId ?? ""}
              onChange={(event) => handleCompanyFilter(event.target.value ? Number(event.target.value) : null)}
            >
              <option value="">全部企业</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
            <button className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700" onClick={() => void refreshProducts()} type="button">
              刷新
            </button>
          </div>
          {loading ? (
            <LoadingState label="正在加载产品" rows={4} />
          ) : products.length === 0 ? (
            <EmptyState title="暂无产品" description="创建产品或导入 product_catalog.csv 后将显示在这里。" />
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-200">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">产品</th>
                    <th className="px-4 py-3 font-semibold">企业</th>
                    <th className="px-4 py-3 font-semibold">品类</th>
                    <th className="px-4 py-3 font-semibold">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 bg-white">
                  {products.map((product) => (
                    <tr key={product.id} className={selectedProductId === product.id ? "bg-river/5" : undefined}>
                      <td className="px-4 py-3">
                        <p className="font-medium text-ink">{product.product_name_cn}</p>
                        <p className="mt-1 text-xs text-slate-500">{product.product_name_en ?? "-"}</p>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{companyName(companies, product.company_id)}</td>
                      <td className="px-4 py-3 text-slate-600">{product.category ?? "-"}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <button className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700" onClick={() => { setSelectedProductId(product.id); setKeywordResult(null); }} type="button">
                            详情
                          </button>
                          <button className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-river" onClick={() => startEdit(product)} type="button">
                            编辑
                          </button>
                          <button className="rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700" onClick={() => void handleDelete(product)} type="button">
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="产品详情与关键词">
          {selectedProduct ? (
            <div className="grid gap-5">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <h3 className="text-base font-semibold text-ink">{selectedProduct.product_name_cn}</h3>
                <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                  <DetailItem label="英文名" value={selectedProduct.product_name_en} />
                  <DetailItem label="企业" value={companyName(companies, selectedProduct.company_id)} />
                  <DetailItem label="品类" value={selectedProduct.category} />
                  <DetailItem label="成本价" value={formatValue(selectedProduct.cost_price_cny, " CNY")} />
                  <DetailItem label="重量" value={formatValue(selectedProduct.weight_kg, " kg")} />
                  <DetailItem label="MOQ" value={selectedProduct.moq === null ? null : String(selectedProduct.moq)} />
                  <DetailItem label="包装尺寸" value={selectedProduct.package_size} />
                  <DetailItem label="认证" value={selectedProduct.certification} />
                </dl>
                {selectedProduct.description ? <p className="mt-3 text-sm leading-6 text-slate-600">{selectedProduct.description}</p> : null}
              </div>
              <div className="grid gap-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextInput label="目标国家" value={keywordForm.target_country} onChange={(value) => setKeywordForm({ ...keywordForm, target_country: value })} />
                  <TextInput label="目标平台" value={keywordForm.target_platforms} onChange={(value) => setKeywordForm({ ...keywordForm, target_platforms: value })} />
                </div>
                <button
                  className="w-fit rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={generating}
                  onClick={() => void handleGenerateKeywords()}
                  type="button"
                >
                  {generating ? "生成中" : "生成产品关键词"}
                </button>
                {keywordResult ? <KeywordResult result={keywordResult} /> : null}
              </div>
            </div>
          ) : (
            <EmptyState title="未选择产品" description="在产品列表中选择一条记录后可查看详情并生成关键词。" />
          )}
        </Panel>
        {notice ? <p className="rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
        {error ? <ErrorState message={error} /> : null}
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

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-slate-500">{label}</dt>
      <dd className="mt-1 text-slate-700">{value || "-"}</dd>
    </div>
  );
}

function ImportResult({ result }: { result: CsvImportResult }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-2 text-sm sm:grid-cols-4">
        <DetailItem label="文件" value={result.file_name} />
        <DetailItem label="模式" value={result.mode === "validate" ? "校验" : "导入"} />
        <DetailItem label="有效行" value={`${result.valid_rows}/${result.total_rows}`} />
        <DetailItem label="已导入" value={String(result.inserted)} />
      </div>
      {result.errors.length > 0 ? (
        <div className="mt-4 overflow-hidden rounded-lg border border-red-200">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-red-50 text-red-700">
              <tr>
                <th className="px-3 py-2 font-semibold">行号</th>
                <th className="px-3 py-2 font-semibold">字段</th>
                <th className="px-3 py-2 font-semibold">错误</th>
                <th className="px-3 py-2 font-semibold">原值</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-red-100 bg-white">
              {result.errors.map((error, index) => (
                <tr key={`${error.row_number}-${error.field}-${index}`}>
                  <td className="px-3 py-2">{error.row_number ?? "-"}</td>
                  <td className="px-3 py-2">{error.field ?? "-"}</td>
                  <td className="px-3 py-2">{error.message}</td>
                  <td className="px-3 py-2">{error.raw_value ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function KeywordResult({ result }: { result: ProductKeywordGenerationResponse }) {
  return (
    <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <DetailItem label="英文产品名" value={result.product_name_en} />
      <ChipGroup label="英文关键词" values={result.keywords_en} />
      <ChipGroup label="日文关键词" values={result.keywords_jp} />
      <ChipGroup label="目标用户" values={result.target_users} />
      <ChipGroup label="卖点" values={result.selling_points} />
      <ChipGroup label="风险提示" values={result.risk_notes} tone="warning" />
    </div>
  );
}

function ChipGroup({ label, values, tone = "default" }: { label: string; values: string[]; tone?: "default" | "warning" }) {
  const toneClass = tone === "warning" ? "border-wheat/50 bg-wheat/10 text-ink" : "border-slate-200 bg-white text-slate-700";
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.map((value) => (
          <span key={value} className={`rounded-md border px-2.5 py-1 text-xs ${toneClass}`}>
            {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function toProductPayload(form: ProductFormState): ProductPayload {
  return {
    company_id: Number(form.company_id),
    product_name_cn: form.product_name_cn.trim(),
    product_name_en: optionalText(form.product_name_en),
    category: optionalText(form.category),
    cost_price_cny: optionalText(form.cost_price_cny),
    weight_kg: optionalText(form.weight_kg),
    package_size: optionalText(form.package_size),
    material: optionalText(form.material),
    certification: optionalText(form.certification),
    moq: optionalInt(form.moq),
    description: optionalText(form.description),
  };
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function optionalInt(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

function splitList(value: string): string[] | null {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length > 0 ? items : null;
}

function companyName(companies: Company[], companyId: number): string {
  return companies.find((company) => company.id === companyId)?.name ?? `企业 #${companyId}`;
}

function formatValue(value: string | null, suffix: string): string | null {
  return value ? `${value}${suffix}` : null;
}
