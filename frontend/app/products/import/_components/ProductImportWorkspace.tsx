"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ProductDraftEditor } from "@/components/product-intake/ProductDraftEditor";
import { EmptyState } from "@/app/_components/EmptyState";
import { ErrorState } from "@/app/_components/ErrorState";
import { FallbackNotice } from "@/app/_components/FallbackNotice";
import { LoadingState } from "@/app/_components/LoadingState";
import { useI18n } from "@/app/_components/LanguageProvider";
import {
  Company,
  ProductDraft,
  ProductImageRole,
  ProductImportAsset,
  ProductIntakeAiResultType,
  ProductIntakeEvidenceSource,
  ProductIntakeSourcePlatform,
  ProductScreenshotsIntakeResponse,
  ProductUrlIntakeResponse,
  getFriendlyErrorMessage,
  getProductIntakeDraft,
  importProductIntakeUrl,
  listCompanies,
  uploadProductIntakeScreenshots,
} from "@/app/_lib/api-client";

type ImportTab = "screenshot" | "url";
type LocalImageStatus = "selected" | "uploading" | "uploaded" | "error";

type ProductImportWorkspaceProps = {
  initialCompanyId?: number | null;
};

type LocalProductImage = {
  id: string;
  file: File;
  previewUrl: string;
  role: ProductImageRole;
  status: LocalImageStatus;
  error: string | null;
  width: number | null;
  height: number | null;
};

type ImportStatus = {
  source: "screenshot" | "url";
  status: string;
  detail: string;
  draftId: number;
  jobId: number;
  lowConfidence: boolean;
  aiResultType: ProductIntakeAiResultType;
  aiFallbackUsed: boolean;
  modelUsed: string | null;
  confidenceScore: string | null;
  assets: ProductImportAsset[];
  multiImageSummary: MultiImageSummary | null;
};

type MultiImageFailure = {
  image_index: number;
  image_role: string;
  code: string | null;
  message: string | null;
};

type MultiImageSummary = {
  image_count: number | null;
  primary_image_asset_id: number | null;
  analysis_strategy: string | null;
  image_roles: string[];
  failed_images: MultiImageFailure[];
  summary: string | null;
};

type Locale = "zh-CN" | "en";

const MAX_SCREENSHOT_IMAGES = 8;
const ACCEPTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const ACCEPTED_IMAGE_LABEL = "PNG/JPG/WebP";

const IMAGE_ROLE_OPTIONS: Array<{ value: ProductImageRole; zh: string; en: string }> = [
  { value: "main", zh: "主图", en: "Main" },
  { value: "spec", zh: "规格图", en: "Specification" },
  { value: "detail", zh: "详情图", en: "Detail" },
  { value: "package", zh: "包装图", en: "Packaging" },
  { value: "other", zh: "其他", en: "Other" },
];

const SCREENSHOT_PLATFORM_OPTIONS: Array<{ labelZh: string; labelEn: string; value: ProductIntakeSourcePlatform }> = [
  { labelZh: "淘宝", labelEn: "Taobao", value: "taobao" },
  { labelZh: "拼多多", labelEn: "Pinduoduo", value: "pinduoduo" },
  { labelZh: "京东", labelEn: "JD", value: "jd" },
  { labelZh: "其他", labelEn: "Other", value: "unknown" },
];

const EVIDENCE_SOURCE_LABELS: Record<ProductIntakeEvidenceSource, { zh: string; en: string }> = {
  screenshot_text: { zh: "截图文本", en: "Screenshot text" },
  screenshot_visual: { zh: "截图视觉", en: "Screenshot visual" },
  url_text: { zh: "链接文本", en: "URL text" },
  manual_text: { zh: "手动文本", en: "Manual text" },
  model_inference: { zh: "模型推断", en: "Model inference" },
};

const NEEDS_SCREENSHOT_MESSAGE_ZH = "该平台页面可能需要登录或动态渲染，请上传商品截图继续分析。";
const NEEDS_SCREENSHOT_MESSAGE_EN = "This page may require login or dynamic rendering. Upload product screenshots to continue.";
const SCREENSHOT_UPLOAD_ERROR_MESSAGE_ZH = "截图上传失败，请检查图片后重试，或稍后再试。";
const SCREENSHOT_UPLOAD_ERROR_MESSAGE_EN = "Screenshot upload failed. Check the images and try again later.";

export function ProductImportWorkspace({ initialCompanyId = null }: ProductImportWorkspaceProps) {
  const router = useRouter();
  const { text, locale } = useI18n();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const previewUrlsRef = useRef<Set<string>>(new Set());
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ImportTab>("screenshot");
  const [screenshotPlatform, setScreenshotPlatform] = useState<ProductIntakeSourcePlatform>("taobao");
  const [selectedImages, setSelectedImages] = useState<LocalProductImage[]>([]);
  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [productUrl, setProductUrl] = useState("");
  const [selectedDraft, setSelectedDraft] = useState<ProductDraft | null>(null);
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const [needsScreenshot, setNeedsScreenshot] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState<ImportTab | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const detectedPlatform = useMemo(() => detectPlatformFromUrl(productUrl, locale), [locale, productUrl]);
  const activeImage = selectedImages.find((image) => image.id === activeImageId) ?? selectedImages[0] ?? null;
  const validImageCount = selectedImages.length;
  const canUploadMore = validImageCount < MAX_SCREENSHOT_IMAGES && submitting === null;
  const imageCountLabel = `${validImageCount}/${MAX_SCREENSHOT_IMAGES}`;

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
    if (selectedImages.length === 0) {
      if (activeImageId !== null) {
        setActiveImageId(null);
      }
      return;
    }
    if (!activeImageId || !selectedImages.some((image) => image.id === activeImageId)) {
      setActiveImageId(selectedImages[0].id);
    }
  }, [activeImageId, selectedImages]);

  useEffect(() => {
    const previewUrls = previewUrlsRef.current;
    return () => {
      previewUrls.forEach((previewUrl) => URL.revokeObjectURL(previewUrl));
      previewUrls.clear();
    };
  }, []);

  function handleScreenshotFileChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.currentTarget.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (submitting !== null) {
      return;
    }
    addFiles(Array.from(event.dataTransfer.files ?? []));
  }

  function addFiles(files: File[]) {
    if (files.length === 0) {
      return;
    }
    setError(null);
    setSelectedDraft(null);
    setImportStatus(null);
    setNeedsScreenshot(false);

    setSelectedImages((current) => {
      const remainingSlots = MAX_SCREENSHOT_IMAGES - current.length;
      if (remainingSlots <= 0) {
        setError(text("已达到 8 张上限，请先删除图片。", "The 8 image limit has been reached. Delete an image first."));
        return current;
      }

      const accepted: LocalProductImage[] = [];
      const rejectedNames: string[] = [];
      let hasMain = current.some((image) => image.role === "main");

      files.slice(0, remainingSlots).forEach((file) => {
        if (!ACCEPTED_IMAGE_TYPES.has(file.type) || file.size <= 0) {
          rejectedNames.push(file.name);
          return;
        }
        const previewUrl = URL.createObjectURL(file);
        previewUrlsRef.current.add(previewUrl);
        const role: ProductImageRole = hasMain ? "detail" : "main";
        hasMain = true;
        accepted.push({
          id: createLocalImageId(),
          file,
          previewUrl,
          role,
          status: "selected",
          error: null,
          width: null,
          height: null,
        });
      });

      if (files.length > remainingSlots) {
        setError(text("一次最多上传 8 张图片，已忽略多余图片。", "You can upload up to 8 images. Extra images were ignored."));
      } else if (rejectedNames.length > 0) {
        setError(
          text(
            `以下文件不是受支持的图片或为空：${rejectedNames.join("、")}`,
            `These files are not supported images or are empty: ${rejectedNames.join(", ")}`,
          ),
        );
      }

      const next = [...current, ...accepted];
      if (!activeImageId && accepted[0]) {
        setActiveImageId(accepted[0].id);
      }
      return next;
    });
  }

  function updateImageDimensions(imageId: string, width: number, height: number) {
    setSelectedImages((current) =>
      current.map((image) => (image.id === imageId ? { ...image, width, height } : image)),
    );
  }

  function removeImage(imageId: string) {
    setSelectedImages((current) => {
      const removed = current.find((image) => image.id === imageId);
      if (removed) {
        URL.revokeObjectURL(removed.previewUrl);
        previewUrlsRef.current.delete(removed.previewUrl);
      }
      const next = current.filter((image) => image.id !== imageId);
      if (!next.some((image) => image.role === "main") && next[0]) {
        next[0] = { ...next[0], role: "main" };
      }
      return next;
    });
  }

  function moveImage(imageId: string, direction: -1 | 1) {
    setSelectedImages((current) => {
      const index = current.findIndex((image) => image.id === imageId);
      const targetIndex = index + direction;
      if (index < 0 || targetIndex < 0 || targetIndex >= current.length) {
        return current;
      }
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(targetIndex, 0, item);
      return next;
    });
  }

  function setPrimaryImage(imageId: string) {
    setSelectedImages((current) =>
      current.map((image) => ({
        ...image,
        role: image.id === imageId ? "main" : image.role === "main" ? "detail" : image.role,
      })),
    );
  }

  function changeImageRole(imageId: string, role: ProductImageRole) {
    if (role === "main") {
      setPrimaryImage(imageId);
      return;
    }
    setSelectedImages((current) => {
      const target = current.find((image) => image.id === imageId);
      if (!target) {
        return current;
      }
      if (target.role !== "main") {
        return current.map((image) => (image.id === imageId ? { ...image, role } : image));
      }
      const replacement = current.find((image) => image.id !== imageId);
      if (!replacement) {
        return current;
      }
      return current.map((image) => {
        if (image.id === imageId) {
          return { ...image, role };
        }
        if (image.id === replacement.id) {
          return { ...image, role: "main" };
        }
        return image;
      });
    });
  }

  async function handleScreenshotSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCompanyId) {
      setError(text("请先选择企业。", "Select a company first."));
      return;
    }
    if (selectedImages.length === 0) {
      setError(text("请先上传商品图片。", "Upload product images first."));
      return;
    }

    setSubmitting("screenshot");
    setError(null);
    setNotice(text("正在上传图片并识别商品信息。", "Uploading images and extracting product information."));
    setSelectedDraft(null);
    setImportStatus(null);
    setNeedsScreenshot(false);
    setSelectedImages((current) => current.map((image) => ({ ...image, status: "uploading", error: null })));
    try {
      const response = await uploadProductIntakeScreenshots({
        company_id: selectedCompanyId,
        files: selectedImages.map((image) => image.file),
        source_platform: screenshotPlatform,
        image_roles: selectedImages.map((image) => image.role),
      });
      const draft = await getProductIntakeDraft(response.draft_id);
      setSelectedDraft(draft);
      setImportStatus(statusFromScreenshotsResponse(response, draft, locale));
      applyUploadResult(response, draft);
      setNotice(noticeFromAiResult(response.ai_result_type, "screenshot", response.error_message, locale));
    } catch (requestError) {
      setSelectedImages((current) => current.map((image) => ({ ...image, status: "selected" })));
      setError(sanitizeScreenshotError(getFriendlyErrorMessage(requestError), locale));
      setNotice(null);
    } finally {
      setSubmitting(null);
    }
  }

  function applyUploadResult(response: ProductScreenshotsIntakeResponse, draft: ProductDraft) {
    const uploadedIndices = new Set(response.assets.map((asset) => asset.image_index));
    const failures = summaryFromDraft(draft)?.failed_images ?? [];
    const failureByIndex = new Map(failures.map((failure) => [failure.image_index, failure]));
    setSelectedImages((current) =>
      current.map((image, index) => {
        const failure = failureByIndex.get(index);
        if (failure) {
          return {
            ...image,
            status: "error",
            error: failure.code ?? text("需要人工复核", "Needs manual review"),
          };
        }
        return {
          ...image,
          status: uploadedIndices.has(index) || uploadedIndices.size === 0 ? "uploaded" : "selected",
          error: null,
        };
      }),
    );
  }

  async function handleUrlSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCompanyId) {
      setError(text("请先选择企业。", "Select a company first."));
      return;
    }
    if (!productUrl.trim()) {
      setError(text("请粘贴淘宝、拼多多或京东商品链接。", "Paste a Taobao, Pinduoduo, or JD product URL."));
      return;
    }

    setSubmitting("url");
    setError(null);
    setNotice(text("正在解析公开商品页面。", "Parsing the public product page."));
    setNeedsScreenshot(false);
    try {
      const response = await importProductIntakeUrl({ company_id: selectedCompanyId, url: productUrl.trim() });
      setImportStatus(statusFromUrlResponse(response, locale));
      if (response.status === "needs_screenshot") {
        setSelectedDraft(null);
        setNeedsScreenshot(true);
        setNotice(text(NEEDS_SCREENSHOT_MESSAGE_ZH, NEEDS_SCREENSHOT_MESSAGE_EN));
        return;
      }
      if (response.status === "failed") {
        setSelectedDraft(null);
        setError(controlledUrlError(response, locale));
        setNotice(null);
        return;
      }
      const draft = await getProductIntakeDraft(response.draft_id);
      setSelectedDraft(draft);
      setNotice(noticeFromAiResult(response.ai_result_type, "url", response.error_message, locale));
    } catch (requestError) {
      setSelectedDraft(null);
      setError(sanitizeTechnicalError(getFriendlyErrorMessage(requestError), locale));
    } finally {
      setSubmitting(null);
    }
  }

  function handleConfirmed(productId: number, companyId: number) {
    router.push(`/products?company_id=${companyId}&product_id=${productId}&intake=confirmed`);
  }

  if (loading) {
    return <LoadingState label={text("正在加载企业", "Loading companies")} rows={4} />;
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
            {text("重新加载", "Reload")}
          </button>
        }
      />
    );
  }

  if (companies.length === 0) {
    return (
      <EmptyState
        title={text("请先创建企业", "Create a company first")}
        description={text("智能导入生成的产品必须归属于企业。", "Imported product drafts must belong to a company.")}
        action={
          <Link className="rounded-md bg-river px-4 py-2 text-sm font-semibold text-white" href="/companies">
            {text("去创建企业", "Create company")}
          </Link>
        }
      />
    );
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[0.92fr_1.08fr]">
      <section className="grid content-start gap-5">
        <Panel title={text("导入方式", "Import method")}>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 bg-slate-50 p-1">
              <button
                className={tabClassName(activeTab === "screenshot")}
                type="button"
                onClick={() => setActiveTab("screenshot")}
              >
                {text("截图导入", "Screenshot import")}
              </button>
              <button
                className={tabClassName(activeTab === "url")}
                type="button"
                onClick={() => setActiveTab("url")}
              >
                {text("商品链接导入", "Product URL import")}
              </button>
            </div>

            {activeTab === "screenshot" ? (
              <form aria-busy={submitting === "screenshot"} className="grid gap-4" onSubmit={handleScreenshotSubmit}>
                <CompanySelect
                  companies={companies}
                  disabled={submitting !== null}
                  label={text("选择企业", "Company")}
                  placeholder={text("选择企业", "Select company")}
                  value={selectedCompanyId}
                  onChange={setSelectedCompanyId}
                />
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">{text("选择平台", "Platform")}</span>
                  <select
                    className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                    disabled={submitting !== null}
                    name="source_platform"
                    value={screenshotPlatform}
                    onChange={(event) => setScreenshotPlatform(event.target.value as ProductIntakeSourcePlatform)}
                  >
                    {SCREENSHOT_PLATFORM_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {locale === "en" ? option.labelEn : option.labelZh}
                      </option>
                    ))}
                  </select>
                </label>
                <FallbackNotice
                  source="screenshot"
                  title={text("上传前请裁剪隐私信息", "Remove private information before upload")}
                  description={text(
                    "请避免截图包含订单号、收货人、手机号、地址、聊天记录、账号头像等隐私信息。",
                    "Avoid order numbers, recipients, phone numbers, addresses, chat records, account avatars, and other private details.",
                  )}
                />

                <label
                  className={`grid cursor-pointer gap-2 rounded-lg border-2 border-dashed p-4 text-center transition ${
                    isDragging
                      ? "border-river bg-river/5"
                      : canUploadMore
                        ? "border-slate-300 bg-slate-50 hover:border-river/60 hover:bg-river/5"
                        : "border-slate-200 bg-slate-100"
                  }`}
                  onDragEnter={(event) => {
                    event.preventDefault();
                    if (canUploadMore) {
                      setIsDragging(true);
                    }
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={handleDrop}
                >
                  <span className="text-sm font-semibold text-ink">
                    {isDragging
                      ? text("松开以上传图片", "Drop to upload images")
                      : text("拖拽或点击上传商品图片", "Drag or click to upload product images")}
                  </span>
                  <span className="text-xs text-slate-500">
                    {text(
                      `最多 8 张，支持 ${ACCEPTED_IMAGE_LABEL}。当前 ${imageCountLabel}`,
                      `Up to 8 images, ${ACCEPTED_IMAGE_LABEL}. Current ${imageCountLabel}`,
                    )}
                  </span>
                  <input
                    ref={inputRef}
                    multiple
                    accept="image/png,image/jpeg,image/webp"
                    className="sr-only"
                    disabled={!canUploadMore}
                    name="files"
                    type="file"
                    onChange={handleScreenshotFileChange}
                  />
                </label>

                <ImageManager
                  activeImage={activeImage}
                  disabled={submitting !== null}
                  images={selectedImages}
                  locale={locale}
                  onDimensions={updateImageDimensions}
                  onMove={moveImage}
                  onRemove={removeImage}
                  onRoleChange={changeImageRole}
                  onSelect={setActiveImageId}
                  onSetPrimary={setPrimaryImage}
                />

                {submitting === "screenshot" ? <LoadingState label={text("正在分析商品图片", "Analyzing product images")} rows={2} /> : null}
                <button
                  className="min-h-11 w-full rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-fit"
                  disabled={!selectedCompanyId || selectedImages.length === 0 || submitting !== null}
                  type="submit"
                >
                  {submitting === "screenshot" ? text("识别中", "Recognizing") : text("开始识别", "Start recognition")}
                </button>
              </form>
            ) : (
              <form className="grid gap-4" onSubmit={handleUrlSubmit}>
                <CompanySelect
                  companies={companies}
                  disabled={submitting !== null}
                  label={text("选择企业", "Company")}
                  placeholder={text("选择企业", "Select company")}
                  value={selectedCompanyId}
                  onChange={setSelectedCompanyId}
                />
                <label className="grid gap-2">
                  <span className="text-sm font-medium text-slate-700">{text("商品链接", "Product URL")}</span>
                  <input
                    className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                    placeholder={text("粘贴淘宝、拼多多或京东商品链接", "Paste a Taobao, Pinduoduo, or JD product URL")}
                    value={productUrl}
                    onChange={(event) => setProductUrl(event.target.value)}
                  />
                </label>
                <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                  {text("自动识别平台：", "Detected platform: ")}
                  <span className="font-semibold text-ink">{detectedPlatform}</span>
                  {text("。仅表示链接来源线索，非平台官方验证。", ". This is only a source hint, not official platform verification.")}
                </p>
                <FallbackNotice
                  source="url"
                  title={text("链接解析失败时请上传截图", "Upload screenshots if URL parsing fails")}
                  description={text(
                    "系统只读取公开可访问页面，不使用登录态、Cookie、验证码服务或模拟登录。",
                    "The system only reads publicly accessible pages and does not use login state, cookies, captcha services, or simulated login.",
                  )}
                />
                {needsScreenshot ? (
                  <div className="grid gap-3">
                    <FallbackNotice
                      source="url"
                      title={text(NEEDS_SCREENSHOT_MESSAGE_ZH, NEEDS_SCREENSHOT_MESSAGE_EN)}
                      description={text(
                        "可切换到截图导入，用可见商品信息继续生成草稿。",
                        "Switch to screenshot import and use visible product information to continue drafting.",
                      )}
                    />
                    <button
                      className="min-h-11 w-full rounded-md border border-river/30 bg-white px-4 py-2.5 text-sm font-semibold text-river sm:w-fit"
                      type="button"
                      onClick={() => setActiveTab("screenshot")}
                    >
                      {text("切换到截图导入", "Switch to screenshot import")}
                    </button>
                  </div>
                ) : null}
                {submitting === "url" ? <LoadingState label={text("正在解析公开商品页面", "Parsing public product page")} rows={2} /> : null}
                <button
                  className="min-h-11 w-full rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-fit"
                  disabled={!selectedCompanyId || !productUrl.trim() || submitting !== null}
                  type="submit"
                >
                  {submitting === "url" ? text("解析中", "Parsing") : text("解析链接", "Parse URL")}
                </button>
              </form>
            )}
          </div>
        </Panel>

        <details className="rounded-lg border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600 shadow-panel sm:p-5" open>
          <summary className="cursor-pointer text-base font-semibold text-ink">{text("合规说明", "Compliance notes")}</summary>
          <ul className="mt-3 grid gap-2">
            <li>{text("仅分析用户主动提供的截图或链接。", "Only analyze screenshots or links actively provided by the user.")}</li>
            <li>{text("不绕过登录、验证码、风控页面或平台访问限制。", "Do not bypass login, captchas, risk-control pages, or platform access limits.")}</li>
            <li>{text("链接解析失败时请上传商品截图继续分析。", "If URL parsing fails, upload product screenshots to continue.")}</li>
            <li>{text("识别结果需人工确认后才会入库。", "Recognition results require human confirmation before saving.")}</li>
            <li>{text("系统不承诺获取平台真实销量。", "The system does not claim access to true platform sales.")}</li>
          </ul>
        </details>
      </section>

      <section className="grid content-start gap-5">
        <Panel title={text("识别状态", "Recognition status")}>
          {importStatus ? <ImportStatusPanel draft={selectedDraft} importStatus={importStatus} locale={locale} /> : (
            <p className="text-sm text-slate-500">
              {text("提交截图或链接后，这里会显示识别进度和草稿状态。", "After submitting images or a URL, recognition progress and draft status appear here.")}
            </p>
          )}
          <div aria-live="polite" role="status">
            {notice ? <p className="mt-4 rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
          </div>
          {error ? (
            <div className="mt-4" role="alert">
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
          <EmptyState
            title={text("等待生成草稿", "Waiting for draft")}
            description={text(
              "截图识别或链接解析完成后，可在这里编辑并确认入库。",
              "After screenshot recognition or URL parsing finishes, edit and confirm the draft here.",
            )}
          />
        )}
      </section>
    </div>
  );
}

function ImageManager({
  activeImage,
  disabled,
  images,
  locale,
  onDimensions,
  onMove,
  onRemove,
  onRoleChange,
  onSelect,
  onSetPrimary,
}: {
  activeImage: LocalProductImage | null;
  disabled: boolean;
  images: LocalProductImage[];
  locale: Locale;
  onDimensions: (imageId: string, width: number, height: number) => void;
  onMove: (imageId: string, direction: -1 | 1) => void;
  onRemove: (imageId: string) => void;
  onRoleChange: (imageId: string, role: ProductImageRole) => void;
  onSelect: (imageId: string) => void;
  onSetPrimary: (imageId: string) => void;
}) {
  if (images.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        {locale === "en" ? "No images selected yet." : "尚未选择图片。"}
      </p>
    );
  }

  const activeIndex = activeImage ? images.findIndex((image) => image.id === activeImage.id) : -1;
  const isPrimary = activeImage?.role === "main";

  return (
    <div className="grid gap-4">
      {activeImage ? (
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
          <div className="relative aspect-[4/3] w-full bg-white">
            <Image
              unoptimized
              alt={`${locale === "en" ? "Product image" : "商品图片"} #${activeIndex + 1} · ${imageRoleLabel(activeImage.role, locale)}`}
              className="object-contain"
              fill
              src={activeImage.previewUrl}
              sizes="(max-width: 1024px) 100vw, 45vw"
              onLoad={(event) => {
                onDimensions(activeImage.id, event.currentTarget.naturalWidth, event.currentTarget.naturalHeight);
              }}
            />
          </div>
          <div className="grid gap-3 border-t border-slate-200 p-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink" title={activeImage.file.name}>
                #{activeIndex + 1} {activeImage.file.name}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {formatFileSize(activeImage.file.size)} · {activeImage.file.type || "-"} · {formatDimensions(activeImage.width, activeImage.height)}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">{locale === "en" ? "Image role" : "图片角色"}</span>
                <select
                  className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={disabled}
                  value={activeImage.role}
                  onChange={(event) => onRoleChange(activeImage.id, event.target.value as ProductImageRole)}
                >
                  {IMAGE_ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {locale === "en" ? option.en : option.zh}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  className="min-h-11 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={disabled || activeIndex <= 0}
                  type="button"
                  onClick={() => onMove(activeImage.id, -1)}
                >
                  {locale === "en" ? "Move up" : "上移"}
                </button>
                <button
                  className="min-h-11 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={disabled || activeIndex < 0 || activeIndex >= images.length - 1}
                  type="button"
                  onClick={() => onMove(activeImage.id, 1)}
                >
                  {locale === "en" ? "Move down" : "下移"}
                </button>
                <button
                  className="min-h-11 rounded-md border border-river/30 px-3 py-2 text-sm font-medium text-river disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                  disabled={disabled || isPrimary}
                  type="button"
                  onClick={() => onSetPrimary(activeImage.id)}
                >
                  {locale === "en" ? "Set primary" : "设为主图"}
                </button>
                <button
                  className="min-h-11 rounded-md border border-red-200 px-3 py-2 text-sm font-medium text-red-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                  disabled={disabled}
                  type="button"
                  onClick={() => onRemove(activeImage.id)}
                >
                  {locale === "en" ? "Delete" : "删除"}
                </button>
              </div>
            </div>
            {activeImage.error ? <p className="rounded-md bg-red-50 px-3 py-2 text-xs font-medium text-red-700">{activeImage.error}</p> : null}
          </div>
        </div>
      ) : null}

      <div className="grid auto-cols-[7.25rem] grid-flow-col gap-3 overflow-x-auto pb-1 sm:grid-flow-row sm:grid-cols-4 sm:overflow-visible">
        {images.map((image, index) => {
          const selected = activeImage?.id === image.id;
          return (
            <button
              key={image.id}
              aria-label={`${locale === "en" ? "Select image" : "选择图片"} #${index + 1}, ${imageRoleLabel(image.role, locale)}, ${statusLabel(image.status, locale)}`}
              className={`min-w-0 rounded-lg border p-2 text-left transition ${
                selected ? "border-river bg-river/5 ring-2 ring-river/15" : "border-slate-200 bg-white hover:border-river/50"
              }`}
              type="button"
              onClick={() => onSelect(image.id)}
            >
              <span className="relative block aspect-square overflow-hidden rounded-md bg-slate-100">
                <Image
                  unoptimized
                  alt=""
                  className="object-cover"
                  fill
                  src={image.previewUrl}
                  sizes="116px"
                />
                {image.role === "main" ? (
                  <span className="absolute left-1 top-1 rounded bg-river px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    {locale === "en" ? "Main" : "主图"}
                  </span>
                ) : null}
              </span>
              <span className="mt-2 block truncate text-xs font-semibold text-ink">#{index + 1} {image.file.name}</span>
              <span className="block truncate text-[11px] text-slate-500">{formatFileSize(image.file.size)}</span>
              <span className="block truncate text-[11px] text-slate-500">{image.file.type || "-"}</span>
              <span className={`mt-1 inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold ${statusClassName(image.status)}`}>
                {statusLabel(image.status, locale)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ImportStatusPanel({ draft, importStatus, locale }: { draft: ProductDraft | null; importStatus: ImportStatus; locale: Locale }) {
  const summary = importStatus.multiImageSummary;
  const failedCount = summary?.failed_images.length ?? 0;
  const acceptedCount = importStatus.assets.length;
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-2 text-xs font-semibold">
        <span className="rounded-md bg-jade/10 px-2.5 py-1 text-jade">{locale === "en" ? "Real Qwen recognition" : "真实 Qwen 识别"}</span>
        <span className="rounded-md bg-wheat/15 px-2.5 py-1 text-ink">{locale === "en" ? "AI fallback draft" : "AI 回退草稿"}</span>
        <span className="rounded-md bg-slate-100 px-2.5 py-1 text-slate-600">{locale === "en" ? "Manual review" : "需要人工处理"}</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <DetailItem label={locale === "en" ? "Source" : "来源"} value={importStatus.source === "screenshot" ? (locale === "en" ? "Screenshot import" : "截图导入") : (locale === "en" ? "Product URL import" : "商品链接导入")} />
        <DetailItem label={locale === "en" ? "Job status" : "任务状态"} value={jobStatusLabel(importStatus.status, locale)} />
        <DetailItem label={locale === "en" ? "AI result" : "AI 结果"} value={aiResultLabel(importStatus.aiResultType, locale)} />
        <DetailItem label="ai_result_type" value={importStatus.aiResultType} />
        <DetailItem label={locale === "en" ? "AI fallback" : "AI 回退"} value={importStatus.aiFallbackUsed ? (locale === "en" ? "Yes" : "是") : (locale === "en" ? "No" : "否")} />
        <DetailItem label="model_used" value={importStatus.modelUsed ?? (locale === "en" ? "Not called" : "未调用")} />
        <DetailItem label="confidence_score" value={importStatus.confidenceScore ?? (locale === "en" ? "Not recorded" : "未记录")} />
        <DetailItem label="draft_id" value={`#${importStatus.draftId}`} />
        <DetailItem label={locale === "en" ? "Job ID" : "任务 ID"} value={`#${importStatus.jobId}`} />
        <DetailItem label={locale === "en" ? "Images" : "图片"} value={`${acceptedCount}${failedCount ? ` / ${failedCount} ${locale === "en" ? "failed" : "失败"}` : ""}`} />
      </div>
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
        {importStatus.detail}
      </p>
      {summary ? <MultiImageSummaryPanel summary={summary} locale={locale} /> : null}
      {importStatus.assets.length > 0 ? <AssetProvenance assets={importStatus.assets} locale={locale} /> : null}
      {draft ? <DraftSummary draft={draft} locale={locale} /> : null}
    </div>
  );
}

function MultiImageSummaryPanel({ summary, locale }: { summary: MultiImageSummary; locale: Locale }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-sm font-semibold text-ink">{locale === "en" ? "Multi-image summary" : "多图摘要"}</h3>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <DetailItem label={locale === "en" ? "Image count" : "图片数量"} value={summary.image_count === null ? "-" : String(summary.image_count)} />
        <DetailItem label={locale === "en" ? "Primary asset" : "主图资产"} value={summary.primary_image_asset_id === null ? "-" : `#${summary.primary_image_asset_id}`} />
        <DetailItem label={locale === "en" ? "Strategy" : "分析策略"} value={summary.analysis_strategy ?? "-"} />
        <DetailItem label={locale === "en" ? "Roles" : "图片角色"} value={summary.image_roles.map((role) => imageRoleLabel(role, locale)).join(" / ") || "-"} />
      </div>
      {summary.failed_images.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {summary.failed_images.map((failure) => (
            <p key={`${failure.image_index}-${failure.code}`} className="rounded-md border border-wheat/40 bg-wheat/10 px-3 py-2 text-xs font-medium text-ink">
              {locale === "en" ? "Image" : "图片"} #{failure.image_index + 1} · {imageRoleLabel(failure.image_role, locale)} · {failure.code ?? "-"}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AssetProvenance({ assets, locale }: { assets: ProductImportAsset[]; locale: Locale }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-ink">{locale === "en" ? "Image provenance" : "图片来源"}</h3>
      <div className="mt-3 grid gap-2">
        {assets.map((asset) => (
          <div key={asset.id} className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs sm:grid-cols-[1fr_auto] sm:items-center">
            <p className="min-w-0 truncate font-semibold text-ink">
              {locale === "en" ? "Image" : "图片"} #{asset.image_index + 1} · {imageRoleLabel(asset.image_role, locale)} · {asset.file_name}
            </p>
            <p className="text-slate-500">
              {formatFileSize(asset.file_size)} · {asset.mime_type} · {formatDimensions(asset.width, asset.height)}
              {asset.is_primary ? ` · ${locale === "en" ? "primary" : "主图"}` : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function DraftSummary({ draft, locale }: { draft: ProductDraft; locale: Locale }) {
  const sellingPoints = draft.selling_points?.selling_points_cn?.join("、") || (locale === "en" ? "Not extracted" : "未提取");
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-ink">{locale === "en" ? "Product draft" : "产品草稿"}</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <DetailItem label={locale === "en" ? "Chinese name" : "商品中文名"} value={draft.product_name_cn || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "English name" : "英文名"} value={draft.product_name_en || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Category" : "类目"} value={draft.category || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Material" : "材质"} value={draft.material || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Price CNY" : "价格 CNY"} value={draft.price_cny || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Package" : "尺寸/包装"} value={draft.package_size || (locale === "en" ? "Not extracted" : "未提取")} />
      </div>
      <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
        {locale === "en" ? "Selling points: " : "卖点："}{sellingPoints}
      </p>
      {draft.evidence && draft.evidence.length > 0 ? <EvidencePreview draft={draft} locale={locale} /> : null}
    </div>
  );
}

function EvidencePreview({ draft, locale }: { draft: ProductDraft; locale: Locale }) {
  return (
    <div className="mt-3 grid gap-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">evidence</h4>
      {draft.evidence?.slice(0, 8).map((item, index) => (
        <div key={`${item.field}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <p className="font-semibold text-ink">
            {item.field}
            {typeof item.image_index === "number" ? ` · ${locale === "en" ? "Image" : "图片"} #${item.image_index + 1}` : ""}
            {item.image_role ? ` · ${imageRoleLabel(item.image_role, locale)}` : ""}
          </p>
          <p className="mt-1 text-slate-500">
            {sourceLabel(item.source, locale)} · {item.value || "-"}
          </p>
        </div>
      ))}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel sm:p-6">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-4 text-sm leading-6 text-slate-600">{children}</div>
    </section>
  );
}

function CompanySelect({
  companies,
  value,
  onChange,
  label,
  placeholder,
  disabled = false,
}: {
  companies: Company[];
  value: number | null;
  onChange: (companyId: number | null) => void;
  label: string;
  placeholder: string;
  disabled?: boolean;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
        disabled={disabled}
        name="company_id"
        required
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
      >
        <option value="">{placeholder}</option>
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
      <p className="mt-1 break-words font-medium text-ink">{value}</p>
    </div>
  );
}

function tabClassName(active: boolean): string {
  return `min-h-10 rounded-md px-3 py-2 text-sm font-semibold transition ${
    active ? "bg-river text-white shadow-sm" : "text-slate-600 hover:bg-white hover:text-ink"
  }`;
}

function statusFromScreenshotsResponse(
  response: ProductScreenshotsIntakeResponse,
  draft: ProductDraft,
  locale: Locale,
): ImportStatus {
  return {
    source: "screenshot",
    status: response.job_status,
    detail: detailFromAiResult(response.ai_result_type, response.error_message, response.low_confidence, locale),
    draftId: response.draft_id,
    jobId: response.import_job_id,
    lowConfidence: response.low_confidence,
    aiResultType: response.ai_result_type,
    aiFallbackUsed: response.ai_fallback_used,
    modelUsed: response.model_used,
    confidenceScore: response.draft.confidence_score,
    assets: response.assets,
    multiImageSummary: summaryFromDraft(draft),
  };
}

function statusFromUrlResponse(response: ProductUrlIntakeResponse, locale: Locale): ImportStatus {
  return {
    source: "url",
    status: response.status,
    detail: detailFromAiResult(response.ai_result_type, response.error_message ?? response.message, response.draft.low_confidence, locale),
    draftId: response.draft_id,
    jobId: response.job_id,
    lowConfidence: response.draft.low_confidence,
    aiResultType: response.ai_result_type,
    aiFallbackUsed: response.ai_fallback_used,
    modelUsed: response.model_used,
    confidenceScore: response.draft.confidence_score,
    assets: [],
    multiImageSummary: summaryFromDraft(response.draft),
  };
}

function aiResultLabel(value: ProductIntakeAiResultType, locale: Locale): string {
  if (value === "real_qwen") {
    return locale === "en" ? "Real Qwen recognition" : "真实 Qwen 识别";
  }
  if (value === "fallback") {
    return locale === "en" ? "AI fallback draft" : "AI 回退草稿";
  }
  return locale === "en" ? "Manual review required" : "需要人工处理";
}

function jobStatusLabel(value: string, locale: Locale): string {
  const labels: Record<string, { zh: string; en: string }> = {
    pending: { zh: "等待处理", en: "Pending" },
    processing: { zh: "处理中", en: "Processing" },
    draft_ready: { zh: "草稿已生成", en: "Draft ready" },
    draft_ready_with_low_confidence: { zh: "低置信度草稿已生成", en: "Low-confidence draft ready" },
    needs_screenshot: { zh: "需要上传商品截图", en: "Screenshot needed" },
    failed: { zh: "解析失败", en: "Failed" },
    confirmed: { zh: "已确认入库", en: "Confirmed" },
  };
  const label = labels[value];
  return label ? (locale === "en" ? label.en : label.zh) : value;
}

function detailFromAiResult(value: ProductIntakeAiResultType, message: string | null, lowConfidence: boolean, locale: Locale): string {
  if (value === "real_qwen") {
    return locale === "en"
      ? "Real Qwen recognition completed. Review the generated draft."
      : "已完成真实 Qwen 调用并生成待确认草稿。";
  }
  if (value === "fallback") {
    return message ?? (locale === "en" ? "Real AI call failed; a low-confidence fallback draft was created." : "真实 AI 调用未成功，已生成低置信度回退草稿。");
  }
  if (message && message !== "draft_ready") {
    return message;
  }
  return lowConfidence
    ? locale === "en"
      ? "A low-confidence draft was generated. Review or complete fields manually."
      : "已生成低置信度草稿，需要人工复核或补全。"
    : locale === "en"
      ? "Review manually before confirming into the product catalog."
      : "需要人工复核后再确认入库。";
}

function controlledUrlError(response: ProductUrlIntakeResponse, locale: Locale): string {
  return sanitizeTechnicalError(
    response.error_message ||
      response.message ||
      (locale === "en" ? "URL parsing failed. Check the link or upload product screenshots." : "链接解析失败，请检查链接后重试，或上传商品截图继续分析。"),
    locale,
  );
}

function sanitizeScreenshotError(message: string, locale: Locale): string {
  if (!message.trim()) {
    return locale === "en" ? SCREENSHOT_UPLOAD_ERROR_MESSAGE_EN : SCREENSHOT_UPLOAD_ERROR_MESSAGE_ZH;
  }
  if (hasTechnicalDetails(message)) {
    return locale === "en" ? SCREENSHOT_UPLOAD_ERROR_MESSAGE_EN : SCREENSHOT_UPLOAD_ERROR_MESSAGE_ZH;
  }
  return message;
}

function sanitizeTechnicalError(message: string, locale: Locale): string {
  const fallback = locale === "en"
    ? "URL parsing failed. Check the link or upload product screenshots."
    : "链接解析失败，请检查链接后重试，或上传商品截图继续分析。";
  if (!message.trim()) {
    return fallback;
  }
  if (hasTechnicalDetails(message)) {
    return fallback;
  }
  return message;
}

function hasTechnicalDetails(message: string): boolean {
  return /traceback|stack\s*trace|exception|file\s+".+",\s+line\s+\d+|at\s+\S+\s*\(|\.(py|ts|tsx|js):\d+|[A-Za-z]:\\|\/(?:app|usr|var|home)\/|node_modules/i.test(
    message,
  );
}

function noticeFromAiResult(value: ProductIntakeAiResultType, source: ImportTab, message: string | null, locale: Locale): string {
  if (value === "real_qwen") {
    if (source === "screenshot") {
      return locale === "en" ? "Real Qwen image recognition completed. Review the draft." : "真实 Qwen 图片识别完成，请复核草稿。";
    }
    return locale === "en" ? "Real Qwen URL analysis completed. Review the draft." : "真实 Qwen 链接分析完成，请复核草稿。";
  }
  if (value === "fallback") {
    return message ?? (locale === "en" ? "Real AI call failed; complete the fallback draft manually before confirming." : "真实 AI 调用未成功，已生成回退草稿，请人工补全后再确认入库。");
  }
  return source === "url"
    ? locale === "en"
      ? "URL parsing was limited. A draft was created for manual completion."
      : "链接解析受限，已创建可人工补全的草稿。"
    : locale === "en"
      ? "A low-confidence draft was generated. Complete it manually before confirming."
      : "已生成低置信度草稿，请人工补全后再确认入库。";
}

function detectPlatformFromUrl(value: string, locale: Locale): string {
  const text = value.trim();
  if (!text) {
    return locale === "en" ? "Waiting for input" : "待输入";
  }
  let parsed: URL;
  try {
    parsed = new URL(text);
  } catch {
    return locale === "en" ? "Waiting to identify" : "待识别";
  }
  const host = parsed.hostname.toLowerCase();
  if (host === "e.tb.cn" || host.endsWith(".e.tb.cn") || host === "tb.cn" || host.endsWith(".tb.cn")) {
    return locale === "en" ? "Taobao" : "淘宝";
  }
  if (host === "tmall.com" || host.endsWith(".tmall.com")) {
    return locale === "en" ? "Tmall" : "天猫";
  }
  if (host === "taobao.com" || host.endsWith(".taobao.com")) {
    return locale === "en" ? "Taobao" : "淘宝";
  }
  if (host === "jd.com" || host.endsWith(".jd.com") || host === "3.cn" || host.endsWith(".3.cn")) {
    return locale === "en" ? "JD" : "京东";
  }
  if (host === "pinduoduo.com" || host.endsWith(".pinduoduo.com") || host === "yangkeduo.com" || host.endsWith(".yangkeduo.com")) {
    return locale === "en" ? "Pinduoduo" : "拼多多";
  }
  return locale === "en" ? "Other" : "其他";
}

function summaryFromDraft(draft: ProductDraft | null): MultiImageSummary | null {
  const value = draft?.multi_image_summary;
  if (!isRecord(value)) {
    return null;
  }
  return {
    image_count: typeof value.image_count === "number" ? value.image_count : null,
    primary_image_asset_id: typeof value.primary_image_asset_id === "number" ? value.primary_image_asset_id : null,
    analysis_strategy: typeof value.analysis_strategy === "string" ? value.analysis_strategy : null,
    image_roles: Array.isArray(value.image_roles) ? value.image_roles.map((role) => String(role)) : [],
    failed_images: Array.isArray(value.failed_images) ? value.failed_images.map(parseFailure).filter((failure): failure is MultiImageFailure => failure !== null) : [],
    summary: typeof value.summary === "string" ? value.summary : null,
  };
}

function parseFailure(value: unknown): MultiImageFailure | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    image_index: typeof value.image_index === "number" ? value.image_index : 0,
    image_role: typeof value.image_role === "string" ? value.image_role : "unknown",
    code: typeof value.code === "string" ? value.code : null,
    message: typeof value.message === "string" ? value.message : null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function imageRoleLabel(role: string, locale: Locale): string {
  const option = IMAGE_ROLE_OPTIONS.find((item) => item.value === role);
  if (option) {
    return locale === "en" ? option.en : option.zh;
  }
  if (role === "screenshot") {
    return locale === "en" ? "Screenshot" : "截图";
  }
  if (role === "unknown") {
    return locale === "en" ? "Unknown" : "未标注";
  }
  return role;
}

function sourceLabel(source: ProductIntakeEvidenceSource, locale: Locale): string {
  const label = EVIDENCE_SOURCE_LABELS[source];
  return locale === "en" ? label.en : label.zh;
}

function statusLabel(status: LocalImageStatus, locale: Locale): string {
  const labels: Record<LocalImageStatus, { zh: string; en: string }> = {
    selected: { zh: "待上传", en: "Ready" },
    uploading: { zh: "识别中", en: "Recognizing" },
    uploaded: { zh: "已识别", en: "Done" },
    error: { zh: "需复核", en: "Review" },
  };
  const label = labels[status];
  return locale === "en" ? label.en : label.zh;
}

function statusClassName(status: LocalImageStatus): string {
  if (status === "uploaded") {
    return "bg-jade/10 text-jade";
  }
  if (status === "error") {
    return "bg-wheat/15 text-ink";
  }
  if (status === "uploading") {
    return "bg-river/10 text-river";
  }
  return "bg-slate-100 text-slate-600";
}

function formatFileSize(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatDimensions(width: number | null, height: number | null): string {
  if (!width || !height) {
    return "-";
  }
  return `${width}x${height}`;
}

function createLocalImageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
