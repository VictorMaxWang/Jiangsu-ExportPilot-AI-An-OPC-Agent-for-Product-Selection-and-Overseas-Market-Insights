"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ProductDraftEditor } from "../../../../components/product-intake/ProductDraftEditor";
import { EmptyState } from "../../../_components/EmptyState";
import { ErrorState } from "../../../_components/ErrorState";
import { FallbackNotice } from "../../../_components/FallbackNotice";
import { LoadingState } from "../../../_components/LoadingState";
import {
  Company,
  ProductDraft,
  ProductIntakeAiResultType,
  ProductIntakeSourcePlatform,
  ProductScreenshotIntakeResponse,
  ProductUrlIntakeResponse,
  getFriendlyErrorMessage,
  getProductIntakeDraft,
  importProductIntakeUrl,
  listCompanies,
  uploadProductIntakeScreenshot,
} from "../../../_lib/api-client";

type ImportTab = "screenshot" | "url";

type ImportStatus = {
  source: "screenshot" | "url";
  title: string;
  status: string;
  detail: string;
  draftId: number;
  jobId: number;
  lowConfidence: boolean;
  aiResultType: ProductIntakeAiResultType;
  aiFallbackUsed: boolean;
  modelUsed: string | null;
};

type ProductImportWorkspaceProps = {
  initialCompanyId?: number | null;
};

const SCREENSHOT_PLATFORM_OPTIONS: Array<{ label: string; value: ProductIntakeSourcePlatform }> = [
  { label: "淘宝", value: "taobao" },
  { label: "拼多多", value: "pinduoduo" },
  { label: "京东", value: "jd" },
  { label: "其他", value: "unknown" },
];

export function ProductImportWorkspace({ initialCompanyId = null }: ProductImportWorkspaceProps) {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ImportTab>("screenshot");
  const [screenshotPlatform, setScreenshotPlatform] = useState<ProductIntakeSourcePlatform>("taobao");
  const [screenshotFile, setScreenshotFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [productUrl, setProductUrl] = useState("");
  const [selectedDraft, setSelectedDraft] = useState<ProductDraft | null>(null);
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const [needsScreenshot, setNeedsScreenshot] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState<ImportTab | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const detectedPlatform = useMemo(() => detectPlatformFromUrl(productUrl), [productUrl]);

  const loadCompanies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listCompanies();
      setCompanies(response.items);
      const targetCompanyId =
        initialCompanyId && response.items.some((company) => company.id === initialCompanyId)
          ? initialCompanyId
          : response.items[0]?.id ?? null;
      setSelectedCompanyId((current) => current ?? targetCompanyId);
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [initialCompanyId]);

  useEffect(() => {
    void loadCompanies();
  }, [loadCompanies]);

  useEffect(() => {
    if (!screenshotFile) {
      setPreviewUrl(null);
      return;
    }
    const nextPreviewUrl = URL.createObjectURL(screenshotFile);
    setPreviewUrl(nextPreviewUrl);
    return () => URL.revokeObjectURL(nextPreviewUrl);
  }, [screenshotFile]);

  async function handleScreenshotSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCompanyId) {
      setError("请先选择企业。");
      return;
    }
    if (!screenshotFile) {
      setError("请先上传商品截图。");
      return;
    }

    setSubmitting("screenshot");
    setError(null);
    setNotice("正在上传截图并识别商品信息。");
    setNeedsScreenshot(false);
    try {
      const response = await uploadProductIntakeScreenshot({
        company_id: selectedCompanyId,
        file: screenshotFile,
        source_platform: screenshotPlatform,
      });
      const draft = await getProductIntakeDraft(response.draft_id);
      setSelectedDraft(draft);
      setImportStatus(statusFromScreenshotResponse(response));
      setNotice(noticeFromAiResult(response.ai_result_type, "screenshot", response.error_message));
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setSubmitting(null);
    }
  }

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCompanyId) {
      setError("请先选择企业。");
      return;
    }
    if (!productUrl.trim()) {
      setError("请粘贴淘宝、拼多多或京东商品链接。");
      return;
    }

    setSubmitting("url");
    setError(null);
    setNotice("正在解析公开商品页面。");
    setNeedsScreenshot(false);
    try {
      const response = await importProductIntakeUrl({ company_id: selectedCompanyId, url: productUrl.trim() });
      const draft = await getProductIntakeDraft(response.draft_id);
      setSelectedDraft(draft);
      setImportStatus(statusFromUrlResponse(response));
      if (response.status === "needs_screenshot") {
        setNeedsScreenshot(true);
        setNotice(noticeFromAiResult(response.ai_result_type, "url", response.error_message));
        return;
      }
      setNotice(noticeFromAiResult(response.ai_result_type, "url", response.error_message));
    } catch (requestError) {
      setError(getFriendlyErrorMessage(requestError));
    } finally {
      setSubmitting(null);
    }
  }

  function handleConfirmed(productId: number, companyId: number) {
    router.push(`/products?company_id=${companyId}&product_id=${productId}`);
  }

  if (loading) {
    return <LoadingState label="正在加载企业" rows={4} />;
  }

  if (error && companies.length === 0) {
    return (
      <ErrorState
        message={error}
        retryAction={
          <button
            className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white"
            type="button"
            onClick={() => void loadCompanies()}
          >
            重新加载
          </button>
        }
      />
    );
  }

  if (companies.length === 0) {
    return (
      <EmptyState
        title="请先创建企业"
        description="智能导入生成的产品必须归属于企业。"
        action={
          <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/companies">
            去创建企业
          </Link>
        }
      />
    );
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
      <section className="grid gap-5">
        <Panel title="导入方式">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 bg-slate-50 p-1">
              <button
                className={tabClassName(activeTab === "screenshot")}
                type="button"
                onClick={() => setActiveTab("screenshot")}
              >
                截图导入
              </button>
              <button
                className={tabClassName(activeTab === "url")}
                type="button"
                onClick={() => setActiveTab("url")}
              >
                链接导入
              </button>
            </div>

            {activeTab === "screenshot" ? (
              <form className="grid gap-4" onSubmit={handleScreenshotSubmit}>
                <CompanySelect companies={companies} value={selectedCompanyId} onChange={setSelectedCompanyId} />
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">选择平台</span>
                  <select
                    className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                    value={screenshotPlatform}
                    onChange={(event) => setScreenshotPlatform(event.target.value as ProductIntakeSourcePlatform)}
                  >
                    {SCREENSHOT_PLATFORM_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <FallbackNotice
                  source="screenshot"
                  title="上传前请裁剪隐私信息"
                  description="请避免截图包含订单号、收货人、手机号、地址、聊天记录、账号头像等隐私信息。"
                />
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">上传图片</span>
                  <input
                    accept="image/png,image/jpeg,image/webp"
                    className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
                    type="file"
                    onChange={(event) => setScreenshotFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                {previewUrl ? (
                  <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                    <Image
                      unoptimized
                      alt="商品截图预览"
                      className="max-h-[420px] w-full object-contain"
                      height={600}
                      src={previewUrl}
                      width={900}
                    />
                  </div>
                ) : null}
                {submitting === "screenshot" ? <LoadingState label="正在分析商品截图" rows={2} /> : null}
                <button
                  className="w-fit rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={!selectedCompanyId || !screenshotFile || submitting !== null}
                  type="submit"
                >
                  {submitting === "screenshot" ? "识别中" : "开始识别"}
                </button>
              </form>
            ) : (
              <form className="grid gap-4" onSubmit={handleUrlSubmit}>
                <CompanySelect companies={companies} value={selectedCompanyId} onChange={setSelectedCompanyId} />
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">商品链接</span>
                  <input
                    className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                    placeholder="https://item.jd.com/..."
                    value={productUrl}
                    onChange={(event) => setProductUrl(event.target.value)}
                  />
                </label>
                <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                  自动识别平台：<span className="font-semibold text-ink">{detectedPlatform}</span>。仅表示链接来源线索，非平台官方验证。
                </p>
                <FallbackNotice
                  source="url"
                  title="链接解析失败时请上传截图"
                  description="系统只读取公开可访问页面，不使用登录态、Cookie、验证码服务或模拟登录。"
                />
                {needsScreenshot ? (
                  <div className="grid gap-3">
                    <FallbackNotice
                      source="url"
                      title="该平台页面可能需要登录或动态渲染，请上传商品截图继续分析。"
                      description="已保留当前草稿，上传截图后可用更完整的可见信息继续分析。"
                    />
                    <button
                      className="w-fit rounded-md border border-river/30 bg-white px-4 py-2.5 text-sm font-semibold text-river"
                      type="button"
                      onClick={() => setActiveTab("screenshot")}
                    >
                      切换到截图导入
                    </button>
                  </div>
                ) : null}
                {submitting === "url" ? <LoadingState label="正在解析公开商品页面" rows={2} /> : null}
                <button
                  className="w-fit rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={!selectedCompanyId || !productUrl.trim() || submitting !== null}
                  type="submit"
                >
                  {submitting === "url" ? "解析中" : "解析链接"}
                </button>
              </form>
            )}
          </div>
        </Panel>

        <Panel title="安全与边界">
          <ul className="grid gap-2 text-sm leading-6 text-slate-700">
            <li>仅分析用户主动提供的截图/链接。</li>
            <li>链接解析失败时请上传截图。</li>
            <li>识别结果需人工确认后才会入库。</li>
            <li>系统不承诺获取平台真实销量。</li>
          </ul>
        </Panel>
      </section>

      <section className="grid gap-5">
        <Panel title="识别状态">
          {importStatus ? (
            <div className="grid gap-3">
              <DetailItem label="来源" value={importStatus.source === "screenshot" ? "截图导入" : "链接导入"} />
              <DetailItem label="任务状态" value={importStatus.status} />
              <DetailItem label="AI 结果" value={aiResultLabel(importStatus.aiResultType)} />
              <DetailItem label="AI 回退" value={importStatus.aiFallbackUsed ? "是" : "否"} />
              <DetailItem label="模型" value={importStatus.modelUsed ?? "未调用"} />
              <DetailItem label="草稿 ID" value={`#${importStatus.draftId}`} />
              <DetailItem label="任务 ID" value={`#${importStatus.jobId}`} />
              <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                {importStatus.detail}
              </p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">提交截图或链接后，这里会显示识别进度和草稿状态。</p>
          )}
          {notice ? <p className="mt-4 rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
          {error ? (
            <div className="mt-4">
              <ErrorState message={error} />
            </div>
          ) : null}
        </Panel>

        {selectedDraft ? (
          <ProductDraftEditor
            draft={selectedDraft}
            onDraftChange={setSelectedDraft}
            onConfirmed={(product) => handleConfirmed(product.id, product.company_id)}
            onRejected={setSelectedDraft}
          />
        ) : (
          <EmptyState title="等待生成草稿" description="截图识别或链接解析完成后，可在这里编辑并确认入库。" />
        )}
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

function CompanySelect({
  companies,
  value,
  onChange,
}: {
  companies: Company[];
  value: number | null;
  onChange: (companyId: number | null) => void;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">选择企业</span>
      <select
        className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
        required
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">选择企业</option>
        {companies.map((company) => (
          <option key={company.id} value={company.id}>
            {company.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 font-medium text-ink">{value}</p>
    </div>
  );
}

function tabClassName(active: boolean): string {
  return `rounded-md px-3 py-2 text-sm font-semibold transition ${
    active ? "bg-river text-white shadow-sm" : "text-slate-600 hover:bg-white hover:text-ink"
  }`;
}

function statusFromScreenshotResponse(response: ProductScreenshotIntakeResponse): ImportStatus {
  return {
    source: "screenshot",
    title: "截图识别",
    status: response.job_status,
    detail: detailFromAiResult(response.ai_result_type, response.error_message, response.low_confidence),
    draftId: response.draft_id,
    jobId: response.import_job_id,
    lowConfidence: response.low_confidence,
    aiResultType: response.ai_result_type,
    aiFallbackUsed: response.ai_fallback_used,
    modelUsed: response.model_used,
  };
}

function statusFromUrlResponse(response: ProductUrlIntakeResponse): ImportStatus {
  return {
    source: "url",
    title: "链接解析",
    status: response.status,
    detail: detailFromAiResult(response.ai_result_type, response.error_message ?? response.message, response.draft.low_confidence),
    draftId: response.draft_id,
    jobId: response.job_id,
    lowConfidence: response.draft.low_confidence,
    aiResultType: response.ai_result_type,
    aiFallbackUsed: response.ai_fallback_used,
    modelUsed: response.model_used,
  };
}

function aiResultLabel(value: ProductIntakeAiResultType): string {
  if (value === "real_qwen") {
    return "真实 Qwen 识别";
  }
  if (value === "fallback") {
    return "AI 回退草稿";
  }
  return "需要人工处理";
}

function detailFromAiResult(value: ProductIntakeAiResultType, message: string | null, lowConfidence: boolean): string {
  if (value === "real_qwen") {
    return "已完成真实 Qwen 调用并生成待确认草稿。";
  }
  if (value === "fallback") {
    return message ?? "真实 AI 调用未成功，已生成低置信度回退草稿。";
  }
  if (message && message !== "draft_ready") {
    return message;
  }
  return lowConfidence ? "已生成低置信度草稿，需要人工复核或补全。" : "需要人工复核后再确认入库。";
}

function noticeFromAiResult(value: ProductIntakeAiResultType, source: ImportTab, message: string | null): string {
  if (value === "real_qwen") {
    return source === "screenshot" ? "真实 Qwen 截图识别完成，请复核草稿。" : "真实 Qwen 链接分析完成，请复核草稿。";
  }
  if (value === "fallback") {
    return message ?? "真实 AI 调用未成功，已生成回退草稿，请人工补全后再确认入库。";
  }
  return source === "url" ? "链接解析受限，已创建可人工补全的草稿。" : "已生成低置信度草稿，请人工补全后再确认入库。";
}

function detectPlatformFromUrl(value: string): string {
  const text = value.trim();
  if (!text) {
    return "待输入";
  }
  let parsed: URL;
  try {
    parsed = new URL(text);
  } catch {
    return "待识别";
  }
  const host = parsed.hostname.toLowerCase();
  if (host === "tmall.com" || host.endsWith(".tmall.com")) {
    return "天猫";
  }
  if (host === "taobao.com" || host.endsWith(".taobao.com")) {
    return "淘宝";
  }
  if (host === "jd.com" || host.endsWith(".jd.com")) {
    return "京东";
  }
  if (host === "pinduoduo.com" || host.endsWith(".pinduoduo.com") || host === "yangkeduo.com" || host.endsWith(".yangkeduo.com")) {
    return "拼多多";
  }
  return "其他";
}
