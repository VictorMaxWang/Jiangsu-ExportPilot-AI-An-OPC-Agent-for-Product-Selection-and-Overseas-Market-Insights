const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Company = {
  id: number;
  name: string;
  region: string | null;
  industry: string | null;
  description: string | null;
  target_countries: string[] | null;
  created_at: string;
  updated_at: string;
};

export type CompanyPayload = {
  name: string;
  region?: string | null;
  industry?: string | null;
  description?: string | null;
  target_countries?: string[] | null;
};

export type CompanyListResponse = {
  items: Company[];
  total: number;
};

export type Product = {
  id: number;
  company_id: number;
  product_name_cn: string;
  product_name_en: string | null;
  category: string | null;
  cost_price_cny: string | null;
  weight_kg: string | null;
  package_size: string | null;
  material: string | null;
  certification: string | null;
  moq: number | null;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductPayload = {
  company_id: number;
  product_name_cn: string;
  product_name_en?: string | null;
  category?: string | null;
  cost_price_cny?: string | null;
  weight_kg?: string | null;
  package_size?: string | null;
  material?: string | null;
  certification?: string | null;
  moq?: number | null;
  description?: string | null;
};

export type ProductListResponse = {
  items: Product[];
  total: number;
};

export type CsvImportMode = "insert" | "validate";

export type CsvImportErrorDetail = {
  row_number: number | null;
  field: string | null;
  message: string;
  raw_value: string | null;
};

export type CsvImportResult = {
  dataset: string;
  file_name: string;
  mode: CsvImportMode;
  source: string;
  total_rows: number;
  valid_rows: number;
  inserted: number;
  failed: number;
  errors: CsvImportErrorDetail[];
};

export type ProductKeywordGenerationRequest = {
  target_country?: string | null;
  target_platforms?: string[];
  persist?: boolean;
};

export type ProductKeywordGenerationResponse = {
  product_name_en: string;
  keywords_en: string[];
  keywords_jp: string[];
  target_users: string[];
  selling_points: string[];
  risk_notes: string[];
  saved_keywords_count: number;
};

export type MarketingGenerateRequest = {
  product: string;
  country: string;
  target_users?: string[];
  selling_points?: string[];
  price_range?: string | null;
  content_themes?: string[];
  risk_notes?: string[];
  analysis_id?: number | null;
  score_id?: number | null;
  persist_to_analysis?: boolean;
};

export type MarketingGenerateResponse = {
  title: string;
  bullet_points: string[];
  seo_keywords: string[];
  short_video_script: string;
  pinterest_keywords: string[];
  platform_listing_advice: string;
  risk_notes: string[];
};

export type Report = {
  id: number;
  analysis_id: number;
  company_id: number;
  title: string;
  content_markdown: string | null;
  content_html: string | null;
  pdf_url: string | null;
  created_at: string;
  updated_at: string;
};

export type ReportListResponse = {
  items: Report[];
  total: number;
};

export type ReportGenerateRequest = {
  analysis_id: number;
  force_regenerate?: boolean;
};

export type ProviderId =
  | "bailian"
  | "worldbank"
  | "gdelt"
  | "youtube"
  | "etsy"
  | "un_comtrade"
  | "csv_fallback"
  | "ebay"
  | "rakuten"
  | "reddit";

export type ProviderCapabilityStatus =
  | "active_no_key"
  | "configured"
  | "not_configured"
  | "optional_no_key_first"
  | "pending_manual_registration"
  | "fallback_only"
  | "disabled"
  | "unavailable";

export type ProviderMvpPriority = "P0" | "P1" | "P2";
export type ProviderTestStatus =
  | "success"
  | "fallback"
  | "pending"
  | "unavailable"
  | "credentials_valid_but_listing_search_requires_oauth_or_approval";

export type ProviderStatusItem = {
  provider: ProviderId;
  display_name: string;
  status: ProviderCapabilityStatus;
  mvp_priority: ProviderMvpPriority;
  default_enabled: boolean;
  fallback: string | null;
  notes: string;
};

export type ProviderStatusResponse = {
  providers: ProviderStatusItem[];
};

export type ProviderTestResponse = {
  provider: ProviderId;
  status: ProviderTestStatus;
  checked_at: string;
  latency_ms: number;
  fallback_used: boolean;
  message: string;
  sample_count: number;
  error_code: string | null;
  configured: boolean;
  live_ping_success: boolean | null;
  live_search_success: boolean | null;
  fallback_available: boolean;
  cache_bypassed: boolean;
  auth_mode: "no_key" | "key" | "fallback" | null;
};

export type AdminRequestOptions = {
  adminPassword?: string;
};

export type AnalysisWorkflowStatus =
  | "waiting"
  | "running"
  | "success"
  | "failed"
  | "fallback_used";

export type AnalysisRunRequest = {
  company_id: number;
  product_ids: number[];
  target_countries: string[];
  competitor_limit?: number;
};

export type AnalysisRunStartResponse = {
  provider: "export_insight_workflow";
  analysis_id: number;
  status: AnalysisWorkflowStatus;
  current_step: string | null;
  status_url: string;
  detail_url: string;
  next_page_url: string | null;
};

export type AnalysisStepLog = {
  step_id: string;
  node: string;
  title: string;
  status: AnalysisWorkflowStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  sources: Array<Record<string, unknown>>;
  fallback_used: boolean;
  fallback_reason: string | null;
  error_code: string | null;
  error_message: string | null;
};

export type AnalysisProviderBreakdownItem = {
  provider: string;
  source_types: string[];
  labels: string[];
  api_invoked: boolean;
  fallback_used: boolean;
};

export type AnalysisScoringSummary = {
  item_count: number;
  top_score: string | number | null;
  top_product_id: number | null;
  top_country: string | null;
  fallback_used: boolean;
  ai_fallback_used: boolean;
};

export type AnalysisStatusResponse = {
  provider: "export_insight_workflow";
  analysis_id: number;
  company_id: number;
  status: AnalysisWorkflowStatus;
  current_step: string | null;
  step_logs: AnalysisStepLog[];
  scoring_summary: AnalysisScoringSummary;
  used_providers: string[];
  fallback_used_providers: string[];
  provider_breakdown: AnalysisProviderBreakdownItem[];
  next_page_url: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
};

export type AnalysisInputProduct = {
  id: number;
  product_name_cn: string;
  product_name_en: string | null;
  category: string | null;
  cost_price_cny: string | number | null;
  weight_kg: string | number | null;
  package_size: string | null;
  material: string | null;
  certification: string | null;
  moq: number | null;
  description: string | null;
};

export type AnalysisScoreItem = {
  id: number | null;
  analysis_id: number;
  product_id: number;
  product_name_cn: string;
  product_name_en: string | null;
  country: string;
  keyword: string;
  total_score: string | number | null;
  rank: number | null;
  reason: string;
  risk: string;
  next_action: string;
  competitor_analysis: Record<string, unknown>;
  evidence: Record<string, unknown>;
};

export type AnalysisDetailResponse = AnalysisStatusResponse & {
  input_products: AnalysisInputProduct[] | null;
  target_countries: string[] | null;
  scores: AnalysisScoreItem[];
  reports: Report[];
  marketing_assets: Array<Record<string, unknown>>;
  workflow_state: Record<string, unknown>;
};

export type DashboardProductScore = {
  product_id: number;
  product_name_cn: string;
  product_name_en: string | null;
  country: string;
  keyword: string | null;
  rank: number | null;
  total_score: string | number | null;
  trend_score: string | number | null;
  price_score: string | number | null;
  market_score: string | number | null;
  supply_score: string | number | null;
  logistics_score: string | number | null;
  content_score: string | number | null;
  fallback_used: boolean;
  ai_fallback_used: boolean;
};

export type DashboardCountryScore = {
  country: string;
  average_score: string | number | null;
  top_score: string | number | null;
  recommendation_count: number;
  top_product_id: number | null;
  top_product_name: string | null;
};

export type DashboardPriceRange = {
  product_id: number;
  product_name: string;
  country: string;
  keyword: string | null;
  min_price: string | number | null;
  median_price: string | number | null;
  avg_price: string | number | null;
  max_price: string | number | null;
  currency: string | null;
  item_count: number;
  competition_level: "low" | "medium" | "high" | "unknown";
  price_suggestion: string | null;
  sample_notice: string;
};

export type DashboardContentTheme = {
  theme: string;
  weight: number;
  product_id: number | null;
  country: string | null;
  keyword: string | null;
  source_item_count: number;
};

export type DashboardRecommendation = {
  rank: number | null;
  product_id: number;
  product_name: string;
  country: string;
  total_score: string | number | null;
  reason: string | null;
  next_action: string | null;
  fallback_used: boolean;
  ai_fallback_used: boolean;
};

export type DashboardRiskCard = {
  title: string;
  severity: "low" | "medium" | "high";
  product_id: number | null;
  product_name: string | null;
  country: string | null;
  message: string;
  source: string;
};

export type DashboardDataSourceUsed = {
  provider: string;
  label: string;
  source_type: string;
  fallback_used: boolean;
  api_invoked: boolean;
  detail: string | null;
};

export type DashboardResponse = {
  analysis_id: number;
  product_scores: DashboardProductScore[];
  country_scores: DashboardCountryScore[];
  price_ranges: DashboardPriceRange[];
  content_themes: DashboardContentTheme[];
  top_recommendations: DashboardRecommendation[];
  risk_cards: DashboardRiskCard[];
  data_sources_used: DashboardDataSourceUsed[];
};

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function listCompanies(): Promise<CompanyListResponse> {
  return requestJson<CompanyListResponse>("/api/companies");
}

export async function createCompany(payload: CompanyPayload): Promise<Company> {
  return requestJson<Company>("/api/companies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateCompany(companyId: number, payload: Partial<CompanyPayload>): Promise<Company> {
  return requestJson<Company>(`/api/companies/${companyId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteCompany(companyId: number): Promise<void> {
  await requestVoid(`/api/companies/${companyId}`, { method: "DELETE" });
}

export async function listProducts(companyId?: number): Promise<ProductListResponse> {
  const query = companyId ? `?company_id=${companyId}` : "";
  return requestJson<ProductListResponse>(`/api/products${query}`);
}

export async function createProduct(payload: ProductPayload): Promise<Product> {
  return requestJson<Product>("/api/products", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateProduct(productId: number, payload: Partial<ProductPayload>): Promise<Product> {
  return requestJson<Product>(`/api/products/${productId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteProduct(productId: number): Promise<void> {
  await requestVoid(`/api/products/${productId}`, { method: "DELETE" });
}

export async function importProductSample(
  companyId: number,
  mode: CsvImportMode,
): Promise<CsvImportResult> {
  return requestJson<CsvImportResult>("/api/products/import", {
    method: "POST",
    body: JSON.stringify({ company_id: companyId, mode }),
  });
}

export async function importProductUpload(
  companyId: number,
  mode: CsvImportMode,
  file: File,
): Promise<CsvImportResult> {
  const formData = new FormData();
  formData.set("company_id", String(companyId));
  formData.set("mode", mode);
  formData.set("file", file);
  return requestJson<CsvImportResult>("/api/products/import", {
    method: "POST",
    body: formData,
    headers: {},
  });
}

export async function generateProductKeywords(
  productId: number,
  payload: ProductKeywordGenerationRequest,
): Promise<ProductKeywordGenerationResponse> {
  return requestJson<ProductKeywordGenerationResponse>(`/api/products/${productId}/generate-keywords`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listProviderStatuses(options: AdminRequestOptions = {}): Promise<ProviderStatusResponse> {
  return requestJson<ProviderStatusResponse>("/api/admin/providers/status", {
    headers: buildAdminHeaders(options),
  });
}

export async function testProvider(
  provider: ProviderId,
  options: AdminRequestOptions & { forceLive?: boolean } = {},
): Promise<ProviderTestResponse> {
  const query = options.forceLive ? "?force_live=true" : "";
  return requestJson<ProviderTestResponse>(`/api/admin/providers/test/${provider}${query}`, {
    method: "POST",
    headers: buildAdminHeaders(options),
  });
}

export async function startAnalysisRun(
  payload: AnalysisRunRequest,
  signal?: AbortSignal,
): Promise<AnalysisRunStartResponse> {
  return requestJson<AnalysisRunStartResponse>("/api/analysis/run", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export async function getAnalysisStatus(
  analysisId: number,
  signal?: AbortSignal,
): Promise<AnalysisStatusResponse> {
  return requestJson<AnalysisStatusResponse>(`/api/analysis/${analysisId}/status`, {
    cache: "no-store",
    signal,
  });
}

export async function getAnalysisDetail(
  analysisId: number,
  signal?: AbortSignal,
): Promise<AnalysisDetailResponse> {
  return requestJson<AnalysisDetailResponse>(`/api/analysis/${analysisId}`, {
    cache: "no-store",
    signal,
  });
}

export async function listReports(
  analysisId?: number,
  signal?: AbortSignal,
): Promise<ReportListResponse> {
  const query = analysisId ? `?analysis_id=${analysisId}` : "";
  return requestJson<ReportListResponse>(`/api/reports${query}`, {
    cache: "no-store",
    signal,
  });
}

export async function getReport(reportId: number, signal?: AbortSignal): Promise<Report> {
  return requestJson<Report>(`/api/reports/${reportId}`, {
    cache: "no-store",
    signal,
  });
}

export async function generateReport(
  payload: ReportGenerateRequest,
  signal?: AbortSignal,
): Promise<Report> {
  return requestJson<Report>("/api/reports/generate", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export async function generateMarketingContent(
  payload: MarketingGenerateRequest,
  signal?: AbortSignal,
): Promise<MarketingGenerateResponse> {
  return requestJson<MarketingGenerateResponse>("/api/marketing/generate", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export async function getDashboard(
  analysisId: number,
  signal?: AbortSignal,
): Promise<DashboardResponse> {
  return requestJson<DashboardResponse>(`/api/dashboard/${analysisId}`, {
    cache: "no-store",
    signal,
  });
}

export function getFriendlyErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "操作失败，请稍后重试。";
}

export function getCsvImportResultFromError(error: unknown): CsvImportResult | null {
  if (!(error instanceof ApiError) || !isRecord(error.detail)) {
    return null;
  }
  const detail = error.detail.detail;
  if (!isRecord(detail)) {
    return null;
  }
  if (detail.dataset === "products" && Array.isArray(detail.errors)) {
    return detail as CsvImportResult;
  }
  return null;
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await performRequest(path, init);
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
  await performRequest(path, init);
}

async function performRequest(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const hasFormData = init.body instanceof FormData;
  if (!hasFormData && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(0, "后端不可用，请确认 FastAPI 服务已启动。", error);
  }

  if (!response.ok) {
    const detail = await parseErrorResponse(response);
    throw new ApiError(response.status, buildErrorMessage(response.status, detail), detail);
  }
  return response;
}

async function parseErrorResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function buildErrorMessage(status: number, detail: unknown): string {
  if (status === 401) {
    return "Admin Password 无效或缺失。";
  }
  if (isRecord(detail)) {
    const nested = detail.detail;
    if (isRecord(nested)) {
      if (nested.code === "BAILIAN_NOT_CONFIGURED") {
        return "Bailian is not configured on the backend.";
      }
      if (typeof nested.message === "string") {
        return nested.message;
      }
      if (Array.isArray(nested.errors)) {
        return "CSV 格式错误，请查看错误明细。";
      }
    }
    if (typeof nested === "string") {
      return nested;
    }
  }
  if (status === 404) {
    return "记录不存在或已被删除。";
  }
  if (status === 422) {
    return "提交字段校验失败，请检查表单。";
  }
  return "请求失败，请稍后重试。";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function buildAdminHeaders(options: AdminRequestOptions): HeadersInit {
  if (!options.adminPassword) {
    return {};
  }
  return { "X-Admin-Password": options.adminPassword };
}
