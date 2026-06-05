"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { CompanyDraftEditor } from "@/components/company-intake/CompanyDraftEditor";
import { EmptyState } from "@/app/_components/EmptyState";
import { ErrorState } from "@/app/_components/ErrorState";
import { FallbackNotice } from "@/app/_components/FallbackNotice";
import { LoadingState } from "@/app/_components/LoadingState";
import { useI18n } from "@/app/_components/LanguageProvider";
import {
  CompanyDraft,
  CompanyImageRole,
  CompanyImportAsset,
  CompanyIntakeAiResultType,
  CompanyIntakeEvidenceSource,
  CompanyPhotoIntakeResponse,
  getCompanyIntakeDraft,
  getFriendlyErrorMessage,
  uploadCompanyIntakePhotos,
} from "@/app/_lib/api-client";

type LocalImageStatus = "selected" | "uploading" | "uploaded" | "error";
type Locale = "zh-CN" | "en";

type LocalCompanyImage = {
  id: string;
  file: File;
  previewUrl: string;
  role: CompanyImageRole;
  status: LocalImageStatus;
  error: string | null;
  width: number | null;
  height: number | null;
};

type ImportStatus = {
  status: string;
  detail: string;
  draftId: number;
  jobId: number;
  lowConfidence: boolean;
  aiResultType: CompanyIntakeAiResultType;
  aiFallbackUsed: boolean;
  modelUsed: string | null;
  confidenceScore: string | null;
  nextAction: string;
  assets: CompanyImportAsset[];
};

const MAX_COMPANY_IMAGES = 4;
const ACCEPTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const ACCEPTED_IMAGE_LABEL = "PNG/JPG/WebP";

const IMAGE_ROLE_OPTIONS: Array<{ value: CompanyImageRole; zh: string; en: string }> = [
  { value: "business_card", zh: "企业名片", en: "Business card" },
  { value: "catalog_cover", zh: "目录封面", en: "Catalog cover" },
  { value: "brochure", zh: "宣传册", en: "Brochure" },
  { value: "product_display", zh: "产品展示", en: "Product display" },
  { value: "factory_photo", zh: "工厂照片", en: "Factory photo" },
  { value: "business_license", zh: "营业执照", en: "Business license" },
  { value: "other", zh: "其他", en: "Other" },
];

const SOURCE_PLATFORM_OPTIONS: Array<{ value: string; zh: string; en: string }> = [
  { value: "mobile", zh: "手机拍照", en: "Mobile camera" },
  { value: "catalog", zh: "企业目录", en: "Company catalog" },
  { value: "business_card", zh: "名片", en: "Business card" },
  { value: "trade_show", zh: "展会资料", en: "Trade-show material" },
  { value: "other", zh: "其他", en: "Other" },
];

const EVIDENCE_SOURCE_LABELS: Record<CompanyIntakeEvidenceSource, { zh: string; en: string }> = {
  photo_text: { zh: "照片文本", en: "Photo text" },
  photo_visual: { zh: "照片视觉", en: "Photo visual" },
  manual_text: { zh: "手动文本", en: "Manual text" },
  model_inference: { zh: "模型推断", en: "Model inference" },
};

const UPLOAD_ERROR_MESSAGE_ZH = "企业照片上传失败，请检查图片后重试，或稍后再试。";
const UPLOAD_ERROR_MESSAGE_EN = "Company photo upload failed. Check the images and try again later.";

export function CompanyImportWorkspace() {
  const router = useRouter();
  const { text, locale } = useI18n();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const previewUrlsRef = useRef<Set<string>>(new Set());
  const [sourcePlatform, setSourcePlatform] = useState("mobile");
  const [selectedImages, setSelectedImages] = useState<LocalCompanyImage[]>([]);
  const [activeImageId, setActiveImageId] = useState<string | null>(null);
  const [selectedDraft, setSelectedDraft] = useState<CompanyDraft | null>(null);
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeImage = selectedImages.find((image) => image.id === activeImageId) ?? selectedImages[0] ?? null;
  const validImageCount = selectedImages.length;
  const canUploadMore = validImageCount < MAX_COMPANY_IMAGES && !submitting;
  const imageCountLabel = `${validImageCount}/${MAX_COMPANY_IMAGES}`;

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

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.currentTarget.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (submitting) {
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

    setSelectedImages((current) => {
      const remainingSlots = MAX_COMPANY_IMAGES - current.length;
      if (remainingSlots <= 0) {
        setError(text("已达到 4 张上限，请先删除图片。", "The 4 image limit has been reached. Delete an image first."));
        return current;
      }

      const accepted: LocalCompanyImage[] = [];
      const rejectedNames: string[] = [];
      const sliced = files.slice(0, remainingSlots);

      sliced.forEach((file, index) => {
        if (!ACCEPTED_IMAGE_TYPES.has(file.type) || file.size <= 0) {
          rejectedNames.push(file.name);
          return;
        }
        const previewUrl = URL.createObjectURL(file);
        previewUrlsRef.current.add(previewUrl);
        accepted.push({
          id: createLocalImageId(),
          file,
          previewUrl,
          role: defaultRoleForIndex(current.length + index),
          status: "selected",
          error: null,
          width: null,
          height: null,
        });
      });

      if (files.length > remainingSlots) {
        setError(text("一次最多上传 4 张图片，已忽略多余图片。", "You can upload up to 4 images. Extra images were ignored."));
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
      return current.filter((image) => image.id !== imageId);
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

  function setPrimaryRole(imageId: string) {
    setSelectedImages((current) =>
      current.map((image) => ({
        ...image,
        role: image.id === imageId ? "business_card" : image.role === "business_card" ? "catalog_cover" : image.role,
      })),
    );
  }

  function changeImageRole(imageId: string, role: CompanyImageRole) {
    setSelectedImages((current) => current.map((image) => (image.id === imageId ? { ...image, role } : image)));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedImages.length === 0) {
      setError(text("请先上传或拍摄企业图片。", "Upload or capture company images first."));
      return;
    }

    setSubmitting(true);
    setError(null);
    setNotice(text("正在上传图片并识别企业信息。", "Uploading images and extracting company information."));
    setSelectedDraft(null);
    setImportStatus(null);
    setSelectedImages((current) => current.map((image) => ({ ...image, status: "uploading", error: null })));
    try {
      const response = await uploadCompanyIntakePhotos({
        files: selectedImages.map((image) => image.file),
        source_platform: sourcePlatform,
        image_roles: selectedImages.map((image) => image.role),
      });
      const draft = await getCompanyIntakeDraft(response.draft_id);
      setSelectedDraft(draft);
      setImportStatus(statusFromPhotoResponse(response, draft, locale));
      applyUploadResult(response);
      setNotice(noticeFromAiResult(response.ai_result_type, response.error_message, locale));
    } catch (requestError) {
      setSelectedImages((current) => current.map((image) => ({ ...image, status: "selected" })));
      setError(sanitizeUploadError(getFriendlyErrorMessage(requestError), locale));
      setNotice(null);
    } finally {
      setSubmitting(false);
    }
  }

  function applyUploadResult(response: CompanyPhotoIntakeResponse) {
    const uploadedIndices = new Set(response.assets.map((asset) => asset.image_index));
    setSelectedImages((current) =>
      current.map((image, index) => ({
        ...image,
        status: uploadedIndices.has(index) || uploadedIndices.size === 0 ? "uploaded" : "selected",
        error: null,
      })),
    );
  }

  function handleConfirmed(companyId: number) {
    router.push(`/companies?company_id=${companyId}&intake=confirmed`);
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[0.92fr_1.08fr]">
      <section className="grid content-start gap-5">
        <Panel title={text("上传企业素材", "Upload company material")}>
          <form aria-busy={submitting} className="grid gap-4" onSubmit={handleSubmit}>
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">{text("素材来源", "Source")}</span>
              <select
                className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20"
                disabled={submitting}
                name="source_platform"
                value={sourcePlatform}
                onChange={(event) => setSourcePlatform(event.target.value)}
              >
                {SOURCE_PLATFORM_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {locale === "en" ? option.en : option.zh}
                  </option>
                ))}
              </select>
            </label>

            <FallbackNotice
              source="screenshot"
              title={text("上传前请遮挡隐私和敏感证件号", "Mask private or sensitive document numbers before upload")}
              description={text(
                "请不要上传身份证号、手机号、银行账号、完整统一社会信用代码、详细地址、二维码私密信息或合同金额。系统会对识别出的敏感文本脱敏，草稿仍需人工确认后才会入库。",
                "Do not upload ID numbers, phone numbers, bank accounts, full credit codes, detailed addresses, private QR data, or contract amounts. The system redacts recognized sensitive text, and drafts still require manual confirmation.",
              )}
            />

            <div className="grid gap-3 sm:grid-cols-2">
              <button
                className="min-h-11 rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={!canUploadMore}
                type="button"
                onClick={() => cameraInputRef.current?.click()}
              >
                {text("手机拍照上传", "Take photo")}
              </button>
              <button
                className="min-h-11 rounded-md border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
                disabled={!canUploadMore}
                type="button"
                onClick={() => fileInputRef.current?.click()}
              >
                {text("选择截图/照片", "Choose screenshots")}
              </button>
            </div>

            <input
              ref={cameraInputRef}
              className="sr-only"
              name="camera_files"
              type="file"
              accept="image/*"
              capture="environment"
              disabled={!canUploadMore}
              onChange={handleFileChange}
            />
            <input
              ref={fileInputRef}
              className="sr-only"
              name="files"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              multiple
              disabled={!canUploadMore}
              onChange={handleFileChange}
            />

            <label
              className={`grid min-h-36 cursor-pointer place-items-center rounded-lg border border-dashed p-5 text-center transition ${
                isDragging ? "border-river bg-river/5" : "border-slate-300 bg-slate-50 hover:border-river/60 hover:bg-white"
              } ${!canUploadMore ? "cursor-not-allowed opacity-70" : ""}`}
              onClick={() => {
                if (canUploadMore) {
                  fileInputRef.current?.click();
                }
              }}
              onDragOver={(event) => {
                event.preventDefault();
                if (canUploadMore) {
                  setIsDragging(true);
                }
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
            >
              <span>
                <span className="block text-sm font-semibold text-ink">
                  {text("拖拽或点击上传企业照片", "Drag or click to upload company images")}
                </span>
                <span className="mt-2 block text-xs leading-5 text-slate-500">
                  {text(
                    `支持 ${ACCEPTED_IMAGE_LABEL}，最多 4 张。当前 ${imageCountLabel}`,
                    `${ACCEPTED_IMAGE_LABEL}, up to 4 images. Current ${imageCountLabel}`,
                  )}
                </span>
              </span>
            </label>

            <CompanyImagePreview
              activeImage={activeImage}
              disabled={submitting}
              images={selectedImages}
              locale={locale}
              onChangeRole={changeImageRole}
              onMove={moveImage}
              onRemove={removeImage}
              onSelect={setActiveImageId}
              onSetPrimary={setPrimaryRole}
              onUpdateDimensions={updateImageDimensions}
            />

            <button
              className="min-h-11 rounded-md bg-river px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={submitting || selectedImages.length === 0}
              type="submit"
            >
              {submitting ? text("识别中", "Recognizing") : text("生成企业草稿", "Generate company draft")}
            </button>
          </form>
          {notice ? <p className="mt-4 rounded-lg border border-jade/30 bg-jade/10 p-4 text-sm font-medium text-jade">{notice}</p> : null}
          {error ? <div className="mt-4"><ErrorState message={error} /></div> : null}
        </Panel>
      </section>

      <section className="grid content-start gap-5">
        {submitting ? <LoadingState label={text("正在分析企业图片", "Analyzing company images")} rows={4} /> : null}
        {importStatus ? <ImportStatusPanel draft={selectedDraft} importStatus={importStatus} locale={locale} /> : null}
        {selectedDraft ? (
          <CompanyDraftEditor
            draft={selectedDraft}
            onDraftChange={setSelectedDraft}
            onConfirmed={(company) => handleConfirmed(company.id)}
          />
        ) : !submitting ? (
          <EmptyState
            title={text("等待上传企业照片", "Waiting for company images")}
            description={text(
              "上传后会先生成可编辑草稿，确认前不会创建正式企业。",
              "After upload, the system creates an editable draft. No company is created until confirmation.",
            )}
          />
        ) : null}
      </section>
    </div>
  );
}

function CompanyImagePreview({
  images,
  activeImage,
  locale,
  disabled,
  onSelect,
  onRemove,
  onMove,
  onSetPrimary,
  onChangeRole,
  onUpdateDimensions,
}: {
  images: LocalCompanyImage[];
  activeImage: LocalCompanyImage | null;
  locale: Locale;
  disabled: boolean;
  onSelect: (imageId: string) => void;
  onRemove: (imageId: string) => void;
  onMove: (imageId: string, direction: -1 | 1) => void;
  onSetPrimary: (imageId: string) => void;
  onChangeRole: (imageId: string, role: CompanyImageRole) => void;
  onUpdateDimensions: (imageId: string, width: number, height: number) => void;
}) {
  const activeIndex = activeImage ? images.findIndex((image) => image.id === activeImage.id) : -1;

  if (images.length === 0 || !activeImage) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">
        {locale === "en" ? "No images selected yet." : "尚未选择图片。"}
      </div>
    );
  }

  return (
    <div className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_0.86fr]">
        <div className="grid gap-3">
          <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
            <Image
              fill
              unoptimized
              alt={`${locale === "en" ? "Company image" : "企业图片"} #${activeIndex + 1} · ${imageRoleLabel(activeImage.role, locale)}`}
              className="object-contain"
              sizes="(min-width: 1024px) 44vw, 100vw"
              src={activeImage.previewUrl}
              onLoad={(event) =>
                onUpdateDimensions(
                  activeImage.id,
                  event.currentTarget.naturalWidth,
                  event.currentTarget.naturalHeight,
                )
              }
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span title={activeImage.file.name} className="max-w-full truncate font-semibold text-ink">
              {activeImage.file.name}
            </span>
            <span>{formatFileSize(activeImage.file.size)}</span>
            <span>{activeImage.file.type || "-"}</span>
            <span>{formatDimensions(activeImage.width, activeImage.height)}</span>
            <span className={`rounded-md px-2 py-1 font-semibold ${statusClassName(activeImage.status)}`}>
              {statusLabel(activeImage.status, locale)}
            </span>
          </div>
          {activeImage.error ? <p className="text-xs font-semibold text-red-700">{activeImage.error}</p> : null}
        </div>

        <div className="grid content-start gap-3">
          <label className="grid gap-2">
            <span className="text-sm font-medium text-slate-700">{locale === "en" ? "Image role" : "图片角色"}</span>
            <select
              className="min-h-11 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-river focus:ring-2 focus:ring-river/20 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={disabled}
              value={activeImage.role}
              onChange={(event) => onChangeRole(activeImage.id, event.target.value as CompanyImageRole)}
            >
              {IMAGE_ROLE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {locale === "en" ? option.en : option.zh}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={disabled || activeIndex <= 0}
              type="button"
              onClick={() => onMove(activeImage.id, -1)}
            >
              {locale === "en" ? "Move up" : "上移"}
            </button>
            <button
              className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={disabled || activeIndex >= images.length - 1}
              type="button"
              onClick={() => onMove(activeImage.id, 1)}
            >
              {locale === "en" ? "Move down" : "下移"}
            </button>
            <button
              className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-river disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
              disabled={disabled || activeImage.role === "business_card"}
              type="button"
              onClick={() => onSetPrimary(activeImage.id)}
            >
              {locale === "en" ? "Set primary" : "设为主图"}
            </button>
            <button
              className="min-h-10 rounded-md border border-red-200 px-3 py-2 text-sm font-medium text-red-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
              disabled={disabled}
              type="button"
              onClick={() => onRemove(activeImage.id)}
            >
              {locale === "en" ? "Delete" : "删除"}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {images.map((image, index) => (
          <button
            key={image.id}
            aria-label={`${locale === "en" ? "Select image" : "选择图片"} #${index + 1}, ${imageRoleLabel(image.role, locale)}, ${statusLabel(image.status, locale)}`}
            className={`grid gap-2 rounded-lg border p-2 text-left transition ${
              image.id === activeImage.id ? "border-river bg-river/5" : "border-slate-200 bg-white hover:border-river/50"
            }`}
            type="button"
            onClick={() => onSelect(image.id)}
          >
            <span className="relative aspect-square overflow-hidden rounded-md bg-slate-100">
              <Image
                fill
                unoptimized
                alt={`${locale === "en" ? "Thumbnail" : "缩略图"} #${index + 1}`}
                className="object-cover"
                sizes="120px"
                src={image.previewUrl}
              />
              {image.role === "business_card" || image.role === "business_license" ? (
                <span className="absolute left-1 top-1 rounded bg-river px-1.5 py-0.5 text-[10px] font-semibold text-white">
                  {locale === "en" ? "Primary" : "主图"}
                </span>
              ) : null}
            </span>
            <span className="min-w-0 truncate text-xs font-semibold text-ink" title={image.file.name}>
              #{index + 1} {imageRoleLabel(image.role, locale)}
            </span>
            <span className={`w-fit rounded-md px-2 py-0.5 text-[10px] font-semibold ${statusClassName(image.status)}`}>
              {statusLabel(image.status, locale)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ImportStatusPanel({ draft, importStatus, locale }: { draft: CompanyDraft | null; importStatus: ImportStatus; locale: Locale }) {
  return (
    <div className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-panel sm:p-6">
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
        <span className="rounded-md bg-jade/10 px-2.5 py-1 text-jade">{locale === "en" ? "Real Qwen recognition" : "真实 Qwen 识别"}</span>
        <span className="rounded-md bg-wheat/15 px-2.5 py-1 text-ink">{locale === "en" ? "AI fallback draft" : "AI 回退草稿"}</span>
        <span className="rounded-md bg-slate-100 px-2.5 py-1 text-slate-600">{locale === "en" ? "Manual review" : "需要人工处理"}</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <DetailItem label={locale === "en" ? "Job status" : "任务状态"} value={jobStatusLabel(importStatus.status, locale)} />
        <DetailItem label={locale === "en" ? "AI result" : "AI 结果"} value={aiResultLabel(importStatus.aiResultType, locale)} />
        <DetailItem label="ai_result_type" value={importStatus.aiResultType} />
        <DetailItem label={locale === "en" ? "Next action" : "下一步"} value={nextActionLabel(importStatus.nextAction, locale)} />
        <DetailItem label={locale === "en" ? "AI fallback" : "AI 回退"} value={importStatus.aiFallbackUsed ? (locale === "en" ? "Yes" : "是") : (locale === "en" ? "No" : "否")} />
        <DetailItem label="model_used" value={importStatus.modelUsed ?? (locale === "en" ? "Not called" : "未调用")} />
        <DetailItem label="confidence_score" value={importStatus.confidenceScore ?? (locale === "en" ? "Not recorded" : "未记录")} />
        <DetailItem label="draft_id" value={`#${importStatus.draftId}`} />
        <DetailItem label={locale === "en" ? "Job ID" : "任务 ID"} value={`#${importStatus.jobId}`} />
        <DetailItem label={locale === "en" ? "Images" : "图片"} value={String(importStatus.assets.length)} />
      </div>
      <p className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700">
        {importStatus.detail}
      </p>
      {importStatus.assets.length > 0 ? <AssetProvenance assets={importStatus.assets} locale={locale} /> : null}
      {draft ? <DraftSummary draft={draft} locale={locale} /> : null}
    </div>
  );
}

function AssetProvenance({ assets, locale }: { assets: CompanyImportAsset[]; locale: Locale }) {
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

function DraftSummary({ draft, locale }: { draft: CompanyDraft; locale: Locale }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-ink">{locale === "en" ? "Company draft preview" : "企业草稿预览"}</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <DetailItem label={locale === "en" ? "Company name" : "企业名称"} value={draft.company_name || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Region" : "地区"} value={draft.region || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Industry" : "行业"} value={draft.industry || (locale === "en" ? "Not extracted" : "未提取")} />
        <DetailItem label={locale === "en" ? "Target markets" : "目标市场建议"} value={draft.target_countries?.join(", ") || (locale === "en" ? "Not extracted" : "未提取")} />
      </div>
      <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
        {locale === "en" ? "Main products: " : "主营产品："}{draft.main_products?.join("、") || (locale === "en" ? "Not extracted" : "未提取")}
      </p>
      {draft.description ? <p className="mt-3 text-sm leading-6 text-slate-600">{draft.description}</p> : null}
      {draft.evidence && draft.evidence.length > 0 ? <EvidencePreview draft={draft} locale={locale} /> : null}
    </div>
  );
}

function EvidencePreview({ draft, locale }: { draft: CompanyDraft; locale: Locale }) {
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

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 break-words font-medium text-ink">{value}</p>
    </div>
  );
}

function statusFromPhotoResponse(response: CompanyPhotoIntakeResponse, draft: CompanyDraft, locale: Locale): ImportStatus {
  return {
    status: response.job_status,
    detail: detailFromAiResult(response.ai_result_type, response.error_message, response.low_confidence, locale),
    draftId: response.draft_id,
    jobId: response.import_job_id,
    lowConfidence: response.low_confidence,
    aiResultType: response.ai_result_type,
    aiFallbackUsed: response.ai_fallback_used,
    modelUsed: response.model_used,
    confidenceScore: draft.confidence_score,
    nextAction: response.next_action,
    assets: response.assets,
  };
}

function aiResultLabel(value: CompanyIntakeAiResultType, locale: Locale): string {
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
    confirmed: { zh: "已确认入库", en: "Confirmed" },
    failed: { zh: "解析失败", en: "Failed" },
  };
  const label = labels[value];
  return label ? (locale === "en" ? label.en : label.zh) : value;
}

function nextActionLabel(value: string, locale: Locale): string {
  const labels: Record<string, { zh: string; en: string }> = {
    review_draft: { zh: "复核草稿", en: "Review draft" },
    manual_review: { zh: "人工复核", en: "Manual review" },
    manual_fill: { zh: "人工补全", en: "Manual fill" },
  };
  const label = labels[value];
  return label ? (locale === "en" ? label.en : label.zh) : value;
}

function detailFromAiResult(value: CompanyIntakeAiResultType, message: string | null, lowConfidence: boolean, locale: Locale): string {
  if (value === "real_qwen") {
    return locale === "en"
      ? "Real Qwen recognition completed. Review the generated company draft."
      : "已完成真实 Qwen 图片识别，请复核企业草稿。";
  }
  if (value === "fallback") {
    return message ?? (locale === "en" ? "Real AI call failed; a manual company draft was created." : "真实 AI 调用未成功，已生成可人工补全的企业草稿。");
  }
  if (message && message !== "draft_ready") {
    return message;
  }
  return lowConfidence
    ? locale === "en"
      ? "A low-confidence company draft was generated. Review or complete fields manually."
      : "已生成低置信度企业草稿，需要人工复核或补全。"
    : locale === "en"
      ? "Review manually before confirming into the company catalog."
      : "需要人工复核后再确认入库。";
}

function noticeFromAiResult(value: CompanyIntakeAiResultType, message: string | null, locale: Locale): string {
  if (value === "real_qwen") {
    return locale === "en" ? "Real Qwen company recognition completed. Review the draft." : "真实 Qwen 企业识别完成，请复核草稿。";
  }
  if (value === "fallback") {
    return message ?? (locale === "en" ? "Real AI call failed; complete the draft manually before confirming." : "真实 AI 调用未成功，请人工补全后再确认入库。");
  }
  return locale === "en"
    ? "A low-confidence company draft was generated. Complete it manually before confirming."
    : "已生成低置信度企业草稿，请人工补全后再确认入库。";
}

function sanitizeUploadError(message: string, locale: Locale): string {
  if (!message.trim()) {
    return locale === "en" ? UPLOAD_ERROR_MESSAGE_EN : UPLOAD_ERROR_MESSAGE_ZH;
  }
  if (hasTechnicalDetails(message)) {
    return locale === "en" ? UPLOAD_ERROR_MESSAGE_EN : UPLOAD_ERROR_MESSAGE_ZH;
  }
  return message;
}

function hasTechnicalDetails(message: string): boolean {
  return /traceback|stack\s*trace|exception|file\s+".+",\s+line\s+\d+|at\s+\S+\s*\(|\.(py|ts|tsx|js):\d+|[A-Za-z]:\\|\/(?:app|usr|var|home)\/|node_modules|key|token|secret|cookie/i.test(
    message,
  );
}

function imageRoleLabel(role: string, locale: Locale): string {
  const option = IMAGE_ROLE_OPTIONS.find((item) => item.value === role);
  if (option) {
    return locale === "en" ? option.en : option.zh;
  }
  if (role === "unknown") {
    return locale === "en" ? "Unknown" : "未标注";
  }
  return role;
}

function sourceLabel(source: CompanyIntakeEvidenceSource, locale: Locale): string {
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

function defaultRoleForIndex(index: number): CompanyImageRole {
  if (index === 0) {
    return "business_card";
  }
  if (index === 1) {
    return "catalog_cover";
  }
  if (index === 2) {
    return "brochure";
  }
  return "other";
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
