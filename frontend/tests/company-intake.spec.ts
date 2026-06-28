import { expect, Page, Request, Route, test } from "@playwright/test";

const confirmedCompany = {
  id: 77,
  name: "苏州出口试点有限公司",
  region: "江苏苏州",
  industry: "家居用品制造",
  description: "Confirmed by Q48 company photo intake frontend test.",
  target_countries: ["US", "JP"],
  created_at: "2026-06-05T00:00:00Z",
  updated_at: "2026-06-05T00:00:00Z",
};

const onePixelPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

test("companies page shows localized photo CTA and selected confirmed company", async ({ page }) => {
  await mockCompanyIntakeApi(page);
  await page.goto("/companies?company_id=77&intake=confirmed");

  const photoCta = page.getByRole("link", { name: "拍照新增企业" });
  await expect(photoCta).toBeVisible();
  await expect(photoCta).toHaveAttribute("href", "/companies/import");
  await expect(page.getByText("企业已确认入库，可继续新增产品或启动智能体分析。")).toBeVisible();
  await expect(page.getByText("苏州出口试点有限公司").first()).toBeVisible();

  await page.goto("/companies/import");
  await expect(page).toHaveURL(/\/companies\/import$/);
});

test("company import page supports camera input and blocks the fifth image", async ({ page }) => {
  await mockCompanyIntakeApi(page);
  await page.goto("/companies/import");

  await expect(page.getByRole("heading", { name: "拍照新增企业" })).toBeVisible();
  await expect(page.locator('input[name="camera_files"]')).toHaveAttribute("accept", "image/*");
  await expect(page.locator('input[name="camera_files"]')).toHaveAttribute("capture", "environment");

  const submitButton = page.getByRole("button", { name: "生成企业草稿" });
  await expect(submitButton).toBeDisabled();

  await page.locator('input[name="files"]').setInputFiles(
    Array.from({ length: 5 }, (_value, index) => imageFile(`company-${index}.png`)),
  );

  await expect(page.getByText("一次最多上传 4 张图片，已忽略多余图片。")).toBeVisible();
  await expect(page.getByText(/当前 4\/4/)).toBeVisible();
  await expect(page.getByTitle("company-0.png").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /选择图片 #4/ })).toBeVisible();
  await expect(page.getByText("company-4.png")).toHaveCount(0);
  await expect(submitButton).toBeEnabled();
});

test("company photo upload posts ordered multipart data and shows draft evidence", async ({ page }) => {
  let photoRequestSeen = false;

  await mockCompanyIntakeApi(page, {
    uploadDelayMs: 300,
    onPhotoRequest(request) {
      const requestUrl = new URL(request.url());
      const contentType = request.headers()["content-type"] ?? "";
      const body = request.postData() ?? "";

      expect(request.method()).toBe("POST");
      expect(requestUrl.pathname).toBe("/api/company-intake/photo");
      expect(contentType).toContain("multipart/form-data");
      expect(body).toContain('name="source_platform"');
      expect(body).toContain("\r\nmobile\r\n");
      expect(fileNamesFromMultipart(body)).toEqual(["business-card.png", "catalog-cover.png"]);
      expect(roleValuesFromMultipart(body)).toEqual(["business_card", "catalog_cover"]);
      photoRequestSeen = true;
    },
  });
  await page.goto("/companies/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("business-card.png"),
    imageFile("catalog-cover.png"),
  ]);
  await page.getByRole("button", { name: "生成企业草稿" }).click();

  await expect(page.getByText("正在分析企业图片")).toBeVisible();
  await expect(page.getByRole("button", { name: "识别中", exact: true })).toBeDisabled();

  await expect(page.getByRole("heading", { name: "企业草稿", exact: true })).toBeVisible();
  expect(photoRequestSeen).toBe(true);
  await expect(page.getByText("draft_id")).toBeVisible();
  await expect(page.getByText("#501")).toBeVisible();
  await expect(page.getByText("ai_result_type")).toBeVisible();
  await expect(page.getByText("real_qwen")).toBeVisible();
  await expect(page.getByText("qwen-vl-test")).toBeVisible();
  await expect(page.getByText("图片 #1 · 企业名片 · business-card.png")).toBeVisible();
  await expect(page.getByText("图片 #2 · 目录封面 · catalog-cover.png")).toBeVisible();
  await expect(page.getByText("company_name · 图片 #1 · 企业名片")).toBeVisible();
  await expect(page.getByText("main_products · 图片 #2 · 目录封面")).toBeVisible();
});

test("draft save preserves evidence image index and role", async ({ page }) => {
  let updatePayload: CompanyDraftUpdatePayload | null = null;

  await mockCompanyIntakeApi(page, {
    onDraftUpdate(payload) {
      updatePayload = payload;
    },
  });
  await page.goto("/companies/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("business-card.png"),
    imageFile("catalog-cover.png"),
  ]);
  await page.getByRole("button", { name: "生成企业草稿" }).click();

  await expect(page.getByRole("heading", { name: "企业草稿", exact: true })).toBeVisible();
  await page.getByLabel("企业名称").fill("苏州确认出口有限公司");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect.poll(() => updatePayload?.company_name).toBe("苏州确认出口有限公司");

  expect(updatePayload?.evidence?.[0]).toMatchObject({
    field: "company_name",
    source: "photo_text",
    image_index: 0,
    image_role: "business_card",
  });
  expect(updatePayload?.evidence?.[1]).toMatchObject({
    field: "main_products",
    source: "photo_visual",
    image_index: 1,
    image_role: "catalog_cover",
  });
});

test("confirming a company draft redirects to selected company success state", async ({ page }) => {
  await mockCompanyIntakeApi(page);
  await page.goto("/companies/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("business-card.png"),
    imageFile("catalog-cover.png"),
  ]);
  await page.getByRole("button", { name: "生成企业草稿" }).click();

  await expect(page.getByRole("heading", { name: "企业草稿", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认入库" }).click();

  await expect(page).toHaveURL(/\/companies\?company_id=77&intake=confirmed$/);
  await expect(page.getByText("企业已确认入库，可继续新增产品或启动智能体分析。")).toBeVisible();
  await expect(page.getByText("苏州出口试点有限公司").first()).toBeVisible();
});

test("mobile viewport supports four selected images without page-level horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockCompanyIntakeApi(page);
  await page.goto("/companies/import");

  await page.locator('input[name="files"]').setInputFiles(
    Array.from({ length: 4 }, (_value, index) => imageFile(`mobile-company-${index}.png`)),
  );

  await expect(page.getByText(/当前 4\/4/)).toBeVisible();
  await expect(page.getByTitle("mobile-company-0.png").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /选择图片 #4/ })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasHorizontalOverflow).toBe(false);
});

type MockCompanyIntakeApiOptions = {
  uploadDelayMs?: number;
  onPhotoRequest?: (request: Request) => void | Promise<void>;
  onDraftUpdate?: (payload: CompanyDraftUpdatePayload) => void;
};

async function mockCompanyIntakeApi(page: Page, options: MockCompanyIntakeApiOptions = {}): Promise<void> {
  const drafts = new Map<number, CompanyDraftFixture>([[501, companyDraftFixture()]]);
  let companyConfirmed = false;

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === "GET" && path === "/api/companies") {
      await fulfillJson(route, {
        items: companyConfirmed ? [confirmedCompany] : [confirmedCompany],
        total: 1,
      });
      return;
    }

    if (method === "POST" && path === "/api/company-intake/photo") {
      await options.onPhotoRequest?.(request);
      if (options.uploadDelayMs) {
        await delay(options.uploadDelayMs);
      }
      await fulfillJson(route, photoResponse(drafts.get(501) ?? companyDraftFixture()), 201);
      return;
    }

    const draftMatch = path.match(/^\/api\/company-intake\/drafts\/(\d+)$/);
    if (draftMatch && method === "GET") {
      await fulfillJson(route, drafts.get(Number(draftMatch[1])));
      return;
    }

    if (draftMatch && method === "PUT") {
      const draftId = Number(draftMatch[1]);
      const current = drafts.get(draftId) ?? companyDraftFixture();
      const patch = (request.postDataJSON() ?? {}) as CompanyDraftUpdatePayload;
      options.onDraftUpdate?.(patch);
      const updated: CompanyDraftFixture = {
        ...current,
        ...patch,
        updated_at: "2026-06-05T01:00:00Z",
      };
      drafts.set(draftId, updated);
      await fulfillJson(route, updated);
      return;
    }

    const confirmMatch = path.match(/^\/api\/company-intake\/drafts\/(\d+)\/confirm$/);
    if (confirmMatch && method === "POST") {
      companyConfirmed = true;
      await fulfillJson(route, confirmedCompany);
      return;
    }

    await fulfillJson(route, { detail: "Unhandled mock API route" }, 404);
  });
}

function photoResponse(draft: CompanyDraftFixture): CompanyPhotoResponseFixture {
  const assets = [
    assetFixture(601, "business-card.png", 0, "business_card", true),
    assetFixture(602, "catalog-cover.png", 1, "catalog_cover", false),
  ];
  return {
    import_job_id: 401,
    draft_id: 501,
    job_status: "draft_ready",
    draft_status: "draft",
    low_confidence: false,
    ai_result_type: "real_qwen",
    ai_fallback_used: false,
    model_used: "qwen-vl-test",
    error_code: null,
    error_message: null,
    next_action: "review_draft",
    asset: assets[0],
    assets,
    draft: draftSummary(draft),
  };
}

function assetFixture(
  id: number,
  fileName: string,
  imageIndex: number,
  imageRole: string,
  isPrimary: boolean,
): CompanyImportAssetFixture {
  return {
    id,
    file_name: fileName,
    mime_type: "image/png",
    file_size: onePixelPng.length,
    width: 1,
    height: 1,
    image_index: imageIndex,
    image_role: imageRole,
    is_primary: isPrimary,
    created_at: "2026-06-05T00:00:00Z",
  };
}

function companyDraftFixture(): CompanyDraftFixture {
  return {
    id: 501,
    import_job_id: 401,
    status: "draft",
    company_name: "苏州出口试点有限公司",
    region: "江苏苏州",
    industry: "家居用品制造",
    target_countries: ["US", "JP"],
    confidence_score: "0.8200",
    confirmed_company_id: null,
    low_confidence: false,
    credit_code_suffix: "DE12",
    main_products: ["收纳篮", "家居收纳"],
    website: "https://example.test/company",
    description: "宣传册显示该企业主营家居收纳用品。",
    contact_role: "export sales",
    evidence: [
      {
        field: "company_name",
        source: "photo_text",
        image_index: 0,
        image_role: "business_card",
        value: "苏州出口试点有限公司",
      },
      {
        field: "main_products",
        source: "photo_visual",
        image_index: 1,
        image_role: "catalog_cover",
        value: "catalog cover shows storage baskets",
      },
    ],
    risk_notes: ["企业信息需人工复核"],
    created_at: "2026-06-05T00:00:00Z",
    updated_at: "2026-06-05T00:00:00Z",
  };
}

function draftSummary(draft: CompanyDraftFixture): CompanyDraftSummaryFixture {
  return {
    id: draft.id,
    status: draft.status,
    company_name: draft.company_name,
    region: draft.region,
    industry: draft.industry,
    target_countries: draft.target_countries,
    confidence_score: draft.confidence_score,
    confirmed_company_id: draft.confirmed_company_id,
    low_confidence: draft.low_confidence,
  };
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function imageFile(name: string): { name: string; mimeType: string; buffer: Buffer } {
  return {
    name,
    mimeType: "image/png",
    buffer: onePixelPng,
  };
}

function fileNamesFromMultipart(body: string): string[] {
  return Array.from(body.matchAll(/filename="([^"]+)"/g)).map((match) => match[1]);
}

function roleValuesFromMultipart(body: string): string[] {
  return Array.from(body.matchAll(/name="image_roles\[\]"\r\n\r\n([^\r]+)/g)).map((match) => match[1]);
}

type CompanyImportAssetFixture = {
  id: number;
  file_name: string;
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  image_index: number;
  image_role: string;
  is_primary: boolean;
  created_at: string;
};

type CompanyDraftSummaryFixture = {
  id: number;
  status: string;
  company_name: string | null;
  region: string | null;
  industry: string | null;
  target_countries: string[] | null;
  confidence_score: string | null;
  confirmed_company_id: number | null;
  low_confidence: boolean;
};

type CompanyIntakeEvidenceFixture = {
  field: string;
  source: string;
  image_index?: number | null;
  image_role?: string | null;
  value: string | null;
};

type CompanyDraftFixture = CompanyDraftSummaryFixture & {
  import_job_id: number;
  credit_code_suffix: string | null;
  main_products: string[] | null;
  website: string | null;
  description: string | null;
  contact_role: string | null;
  evidence: CompanyIntakeEvidenceFixture[];
  risk_notes: string[];
  created_at: string;
  updated_at: string;
};

type CompanyPhotoResponseFixture = {
  import_job_id: number;
  draft_id: number;
  job_status: string;
  draft_status: string;
  low_confidence: boolean;
  ai_result_type: string;
  ai_fallback_used: boolean;
  model_used: string | null;
  error_code: string | null;
  error_message: string | null;
  next_action: string;
  asset: CompanyImportAssetFixture;
  assets: CompanyImportAssetFixture[];
  draft: CompanyDraftSummaryFixture;
};

type CompanyDraftUpdatePayload = Partial<CompanyDraftFixture> & {
  evidence?: CompanyIntakeEvidenceFixture[];
};
