import { expect, Page, Request, Route, test } from "@playwright/test";

const demoCompany = {
  id: 1,
  name: "南通演示家纺",
  region: "江苏南通",
  industry: "Pet supplies",
  description: "Q43 product intake frontend test company.",
  target_countries: ["US", "JP"],
  created_at: "2026-05-29T00:00:00Z",
  updated_at: "2026-05-29T00:00:00Z",
};

const onePixelPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

test("product import page loads in Chinese and screenshot tab accepts multiple local files", async ({ page }) => {
  await mockProductIntakeApi(page);
  await page.goto("/products/import");

  await expect(page.getByRole("heading", { name: "智能商品导入" })).toBeVisible();
  await expect(page.getByRole("button", { name: "截图导入" })).toBeVisible();
  await expect(page.getByLabel("选择企业")).toHaveValue(String(demoCompany.id));

  const submitButton = page.getByRole("button", { name: "开始识别" });
  await expect(submitButton).toBeDisabled();

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("safe-main.png"),
    imageFile("safe-detail.png"),
  ]);

  await expect(page.getByTitle("safe-main.png")).toBeVisible();
  await expect(page.getByRole("button", { name: /选择图片 #2/ })).toBeVisible();
  await expect(page.getByText(/当前 2\/8/)).toBeVisible();
  await expect(submitButton).toBeEnabled();
});

test("multi-image upload posts ordered multipart data and shows draft evidence provenance", async ({ page }) => {
  let screenshotsRequestSeen = false;

  await mockProductIntakeApi(page, {
    screenshotsDelayMs: 300,
    onScreenshotsRequest(request) {
      const requestUrl = new URL(request.url());
      const contentType = request.headers()["content-type"] ?? "";
      const body = request.postData() ?? "";

      expect(request.method()).toBe("POST");
      expect(requestUrl.pathname).toBe("/api/product-intake/screenshots");
      expect(contentType).toContain("multipart/form-data");
      expect(body).toContain('name="company_id"');
      expect(body).toContain("\r\n1\r\n");
      expect(body).toContain('name="source_platform"');
      expect(body).toContain("\r\ntaobao\r\n");
      expect(fileNamesFromMultipart(body)).toEqual(["safe-main.png", "safe-detail.png"]);
      expect(roleValuesFromMultipart(body)).toEqual(["main", "detail"]);
      screenshotsRequestSeen = true;
    },
  });
  await page.goto("/products/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("safe-main.png"),
    imageFile("safe-detail.png"),
  ]);
  await page.getByRole("button", { name: "开始识别" }).click();

  await expect(page.getByText("正在分析商品图片")).toBeVisible();
  await expect(page.getByRole("button", { name: "识别中", exact: true })).toBeDisabled();

  await expect(page.getByRole("heading", { name: "草稿编辑" })).toBeVisible();
  expect(screenshotsRequestSeen).toBe(true);
  await expect(page.getByText("draft_id")).toBeVisible();
  await expect(page.getByText("#101")).toBeVisible();
  await expect(page.getByText("ai_result_type")).toBeVisible();
  await expect(page.getByText("real_qwen")).toBeVisible();
  await expect(page.getByText("qwen-vl-test")).toBeVisible();
  await expect(page.getByText("图片 #1 · 主图 · safe-main.png")).toBeVisible();
  await expect(page.getByText("图片 #2 · 详情图 · safe-detail.png")).toBeVisible();
  await expect(page.getByText("product_name_cn · 图片 #1 · 主图")).toBeVisible();
  await expect(page.getByText("material · 图片 #2 · 详情图")).toBeVisible();
});

test("reorder and set primary change submitted file and role order", async ({ page }) => {
  let requestBody = "";

  await mockProductIntakeApi(page, {
    onScreenshotsRequest(request) {
      requestBody = request.postData() ?? "";
    },
  });
  await page.goto("/products/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("main.png"),
    imageFile("spec.png"),
    imageFile("pack.png"),
  ]);

  await page.getByRole("button", { name: /选择图片 #3/ }).click();
  await page.getByRole("button", { name: "设为主图" }).click();
  await page.getByRole("button", { name: "上移" }).click();
  await page.getByRole("button", { name: "上移" }).click();
  await page.getByRole("button", { name: "开始识别" }).click();

  await expect(page.getByRole("heading", { name: "草稿编辑" })).toBeVisible();
  expect(fileNamesFromMultipart(requestBody)).toEqual(["pack.png", "main.png", "spec.png"]);
  expect(roleValuesFromMultipart(requestBody)).toEqual(["main", "detail", "detail"]);
});

test("client blocks the ninth image while keeping the first eight selectable", async ({ page }) => {
  await mockProductIntakeApi(page);
  await page.goto("/products/import");

  await page.locator('input[name="files"]').setInputFiles(
    Array.from({ length: 9 }, (_value, index) => imageFile(`p-${index}.png`)),
  );

  await expect(page.getByText("一次最多上传 8 张图片，已忽略多余图片。")).toBeVisible();
  await expect(page.getByText(/当前 8\/8/)).toBeVisible();
  await expect(page.getByTitle("p-0.png")).toBeVisible();
  await expect(page.getByRole("button", { name: /选择图片 #8/ })).toBeVisible();
  await expect(page.getByText("p-8.png")).toHaveCount(0);
});

test("partial backend image failure shows manual review and keeps draft editor reachable", async ({ page }) => {
  await mockProductIntakeApi(page, { partialFailure: true });
  await page.goto("/products/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("safe-main.png"),
    imageFile("broken-content.png"),
  ]);
  await page.getByRole("button", { name: "开始识别" }).click();

  await expect(page.getByText("部分图片需人工复核").first()).toBeVisible();
  await expect(page.getByText("图片 #2 · 详情图 · INVALID_IMAGE_CONTENT")).toBeVisible();
  await expect(page.getByRole("heading", { name: "草稿编辑" })).toBeVisible();
  await expect(page.getByText("需复核")).toBeVisible();
});

test("draft save preserves evidence image index and role", async ({ page }) => {
  let updatePayload: DraftUpdatePayload | null = null;

  await mockProductIntakeApi(page, {
    onDraftUpdate(payload) {
      updatePayload = payload;
    },
  });
  await page.goto("/products/import");

  await page.locator('input[name="files"]').setInputFiles([
    imageFile("safe-main.png"),
    imageFile("safe-detail.png"),
  ]);
  await page.getByRole("button", { name: "开始识别" }).click();

  await expect(page.getByRole("heading", { name: "草稿编辑" })).toBeVisible();
  await page.getByLabel("商品中文名").fill("确认宠物凉感垫");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect.poll(() => updatePayload?.product_name_cn).toBe("确认宠物凉感垫");

  expect(updatePayload?.evidence?.[0]).toMatchObject({
    field: "product_name_cn",
    source: "screenshot_text",
    image_index: 0,
    image_role: "main",
  });
  expect(updatePayload?.evidence?.[1]).toMatchObject({
    field: "material",
    source: "screenshot_visual",
    image_index: 1,
    image_role: "detail",
  });
});

test("mobile viewport supports eight selected images without page-level horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockProductIntakeApi(page);
  await page.goto("/products/import");

  await page.locator('input[name="files"]').setInputFiles(
    Array.from({ length: 8 }, (_value, index) => imageFile(`mobile-${index}.png`)),
  );

  await expect(page.getByText(/当前 8\/8/)).toBeVisible();
  await expect(page.getByTitle("mobile-0.png")).toBeVisible();
  await expect(page.getByRole("button", { name: /选择图片 #8/ })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(hasHorizontalOverflow).toBe(false);
});

test("url tab still shows needs_screenshot fallback and switches back to screenshot import", async ({ page }) => {
  await mockProductIntakeApi(page);
  await page.goto("/products/import");

  await page.getByRole("button", { name: "商品链接导入" }).click();
  await page.getByLabel("商品链接").fill("https://item.jd.com/100012043978.html?token=secret-token");

  await expect(page.getByText("自动识别平台：")).toBeVisible();
  await expect(page.getByText("京东")).toBeVisible();

  await page.getByRole("button", { name: "解析链接" }).click();

  await expect(page.getByText("该平台页面可能需要登录或动态渲染，请上传商品截图继续分析。").first()).toBeVisible();
  await page.getByRole("button", { name: "切换到截图导入" }).click();
  await expect(page.getByText("拖拽或点击上传商品图片")).toBeVisible();
});

type MockProductIntakeApiOptions = {
  screenshotsDelayMs?: number;
  partialFailure?: boolean;
  onScreenshotsRequest?: (request: Request) => void | Promise<void>;
  onDraftUpdate?: (payload: DraftUpdatePayload) => void;
};

async function mockProductIntakeApi(page: Page, options: MockProductIntakeApiOptions = {}): Promise<void> {
  const drafts = new Map<number, ProductDraftFixture>([
    [101, screenshotDraft(options.partialFailure)],
    [102, urlNeedsScreenshotDraft()],
  ]);

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === "GET" && path === "/api/companies") {
      await fulfillJson(route, { items: [demoCompany], total: 1 });
      return;
    }

    if (method === "POST" && path === "/api/product-intake/screenshots") {
      await options.onScreenshotsRequest?.(request);
      if (options.screenshotsDelayMs) {
        await delay(options.screenshotsDelayMs);
      }
      await fulfillJson(route, screenshotsResponse(drafts.get(101) ?? screenshotDraft(false), options.partialFailure));
      return;
    }

    if (method === "POST" && path === "/api/product-intake/screenshot") {
      await fulfillJson(route, { detail: "single-image endpoint should not be used" }, 500);
      return;
    }

    if (method === "POST" && path === "/api/product-intake/url") {
      await fulfillJson(route, {
        job_id: 202,
        draft_id: 102,
        status: "needs_screenshot",
        parse_status: "needs_screenshot",
        source_platform: "jd",
        normalized_url: "https://item.jd.com/100012043978.html",
        item_id: "100012043978",
        sku_id: "100012043978",
        message: "请上传截图继续分析",
        ai_result_type: "manual_required",
        ai_fallback_used: false,
        model_used: null,
        error_code: "URL_FETCH_TIMEOUT",
        error_message: "请上传截图继续分析",
        draft: drafts.get(102),
      });
      return;
    }

    const draftMatch = path.match(/^\/api\/product-intake\/drafts\/(\d+)$/);
    if (draftMatch && method === "GET") {
      await fulfillJson(route, drafts.get(Number(draftMatch[1])));
      return;
    }

    if (draftMatch && method === "PUT") {
      const draftId = Number(draftMatch[1]);
      const current = drafts.get(draftId) ?? screenshotDraft(false);
      const patch = (request.postDataJSON() ?? {}) as DraftUpdatePayload;
      options.onDraftUpdate?.(patch);
      const updated: ProductDraftFixture = {
        ...current,
        ...patch,
        selling_points: {
          ...(current.selling_points ?? {}),
          ...(patch.selling_points ?? {}),
        },
        updated_at: "2026-05-29T01:00:00Z",
      };
      drafts.set(draftId, updated);
      await fulfillJson(route, updated);
      return;
    }

    await fulfillJson(route, { detail: "Unhandled mock API route" }, 404);
  });
}

function screenshotsResponse(draft: ProductDraftFixture, partialFailure = false): ProductScreenshotsResponseFixture {
  const assets = partialFailure
    ? [assetFixture(301, "safe-main.png", 0, "main", true)]
    : [
        assetFixture(301, "safe-main.png", 0, "main", true),
        assetFixture(302, "safe-detail.png", 1, "detail", false),
      ];
  return {
    import_job_id: 201,
    draft_id: 101,
    job_status: partialFailure ? "draft_ready_with_low_confidence" : "draft_ready",
    draft_status: "draft",
    low_confidence: partialFailure,
    ai_result_type: partialFailure ? "manual_required" : "real_qwen",
    ai_fallback_used: false,
    model_used: "qwen-vl-test",
    error_code: partialFailure ? "PARTIAL_IMAGE_UPLOAD_FAILED" : null,
    error_message: partialFailure ? "部分图片需人工复核" : null,
    next_action: partialFailure ? "manual_review" : "review_draft",
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
): ProductImportAssetFixture {
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
    created_at: "2026-05-29T00:00:00Z",
  };
}

function screenshotDraft(partialFailure = false): ProductDraftFixture {
  return {
    id: 101,
    import_job_id: 201,
    company_id: demoCompany.id,
    status: "draft",
    product_name_cn: "宠物凉感垫",
    product_name_en: "Imported Pet Cooling Mat",
    category: "Pet supplies",
    price_cny: "39.90",
    cost_price_cny: null,
    weight_kg: "0.450",
    package_size: "28x18x4cm",
    material: "尼龙",
    color_options: ["蓝色"],
    specification: "夏季宠物凉感垫",
    selling_points: {
      selling_points_cn: ["夏季降温"],
      selling_points_en: ["Cooling mat for summer"],
      usage_scenarios: ["home"],
      cross_border_keywords_en: ["pet cooling mat"],
      risk_notes: partialFailure ? ["部分图片需人工复核"] : ["截图信息需人工复核"],
    },
    target_users: ["pet owners"],
    source_platform: "taobao",
    evidence: [
      {
        field: "product_name_cn",
        source: "screenshot_text",
        image_index: 0,
        image_role: "main",
        value: "宠物凉感垫",
      },
      {
        field: "material",
        source: "screenshot_visual",
        image_index: 1,
        image_role: "detail",
        value: "可见产品细节",
      },
    ],
    confidence_score: partialFailure ? "0.5200" : "0.8200",
    image_count: partialFailure ? 1 : 2,
    primary_image_asset_id: 301,
    multi_image_summary: {
      image_count: partialFailure ? 1 : 2,
      primary_image_asset_id: 301,
      analysis_strategy: partialFailure ? "multi_image_partial" : "multi_image",
      image_roles: partialFailure ? ["main"] : ["main", "detail"],
      failed_images: partialFailure
        ? [
            {
              image_index: 1,
              image_role: "detail",
              code: "INVALID_IMAGE_CONTENT",
              message: "图片内容无法识别",
            },
          ]
        : [],
      summary: "Multiple uploaded product images were analyzed as one product draft.",
    },
    confirmed_product_id: null,
    low_confidence: partialFailure,
    created_at: "2026-05-29T00:00:00Z",
    updated_at: "2026-05-29T00:00:00Z",
  };
}

function urlNeedsScreenshotDraft(): ProductDraftFixture {
  return {
    ...screenshotDraft(false),
    id: 102,
    import_job_id: 202,
    product_name_cn: null,
    product_name_en: null,
    category: null,
    price_cny: null,
    material: null,
    color_options: [],
    specification: null,
    selling_points: {
      selling_points_cn: [],
      selling_points_en: [],
      usage_scenarios: [],
      cross_border_keywords_en: [],
      risk_notes: ["请上传截图继续分析"],
    },
    target_users: [],
    source_platform: "jd",
    evidence: [],
    confidence_score: "0.0000",
    image_count: 0,
    primary_image_asset_id: null,
    multi_image_summary: null,
    low_confidence: true,
  };
}

function draftSummary(draft: ProductDraftFixture): ProductDraftSummaryFixture {
  return {
    id: draft.id,
    status: draft.status,
    product_name_cn: draft.product_name_cn,
    product_name_en: draft.product_name_en,
    category: draft.category,
    price_cny: draft.price_cny,
    confidence_score: draft.confidence_score,
    image_count: draft.image_count,
    primary_image_asset_id: draft.primary_image_asset_id,
    confirmed_product_id: draft.confirmed_product_id,
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

type ProductImportAssetFixture = {
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

type ProductDraftSummaryFixture = {
  id: number;
  status: string;
  product_name_cn: string | null;
  product_name_en: string | null;
  category: string | null;
  price_cny: string | null;
  confidence_score: string | null;
  image_count: number;
  primary_image_asset_id: number | null;
  confirmed_product_id: number | null;
  low_confidence: boolean;
};

type EvidenceFixture = {
  field: string;
  source: string;
  image_index?: number | null;
  image_role?: string | null;
  value: string | null;
};

type ProductDraftFixture = ProductDraftSummaryFixture & {
  import_job_id: number;
  company_id: number;
  cost_price_cny: string | null;
  weight_kg: string | null;
  package_size: string | null;
  material: string | null;
  color_options: string[];
  specification: string | null;
  selling_points: {
    selling_points_cn: string[];
    selling_points_en: string[];
    usage_scenarios: string[];
    cross_border_keywords_en: string[];
    risk_notes: string[];
  };
  target_users: string[];
  source_platform: string;
  evidence: EvidenceFixture[];
  multi_image_summary: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

type ProductScreenshotsResponseFixture = {
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
  asset: ProductImportAssetFixture;
  assets: ProductImportAssetFixture[];
  draft: ProductDraftSummaryFixture;
};

type DraftUpdatePayload = Partial<ProductDraftFixture> & {
  evidence?: EvidenceFixture[];
};
