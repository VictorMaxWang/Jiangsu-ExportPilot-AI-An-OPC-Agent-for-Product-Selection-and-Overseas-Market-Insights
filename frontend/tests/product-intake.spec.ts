import { expect, Page, Route, test } from "@playwright/test";

const demoCompany = {
  id: 1,
  name: "南通演示家纺",
  region: "江苏南通",
  industry: "Pet supplies",
  description: "Q16 product intake frontend test company.",
  target_countries: ["US", "JP"],
  created_at: "2026-05-29T00:00:00Z",
  updated_at: "2026-05-29T00:00:00Z",
};

const onePixelPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

test.beforeEach(async ({ page }) => {
  await mockProductIntakeApi(page);
});

test("product import page loads and screenshot tab accepts a local file", async ({ page }) => {
  await page.goto("/products/import");

  await expect(page.getByRole("heading", { name: "智能商品导入" })).toBeVisible();
  await expect(page.getByRole("button", { name: "截图导入" })).toBeVisible();
  await expect(page.getByLabel("选择企业")).toHaveValue(String(demoCompany.id));

  const submitButton = page.getByRole("button", { name: "开始识别" });
  await expect(submitButton).toBeDisabled();

  await page.locator('input[type="file"]').setInputFiles({
    name: "safe-product.png",
    mimeType: "image/png",
    buffer: onePixelPng,
  });

  await expect(page.getByAltText("商品截图预览")).toBeVisible();
  await expect(submitButton).toBeEnabled();
});

test("url tab accepts a domestic product URL and shows needs_screenshot fallback", async ({ page }) => {
  await page.goto("/products/import");

  await page.getByRole("button", { name: "链接导入" }).click();
  await page.getByLabel("商品链接").fill("https://item.jd.com/100012043978.html?token=secret-token");

  await expect(page.getByText("自动识别平台：")).toBeVisible();
  await expect(page.getByText("京东")).toBeVisible();

  await page.getByRole("button", { name: "解析链接" }).click();

  await expect(page.getByText("链接解析受限，已创建可人工补全的草稿。")).toBeVisible();
  await expect(page.getByText("该平台页面可能需要登录或动态渲染，请上传商品截图继续分析。").first()).toBeVisible();

  await page.getByRole("button", { name: "切换到截图导入" }).click();
  await expect(page.getByText("上传图片")).toBeVisible();
});

test("draft edit and confirm redirects to products list with imported product selected", async ({ page }) => {
  await page.goto("/products/import");

  await page.locator('input[type="file"]').setInputFiles({
    name: "safe-product.png",
    mimeType: "image/png",
    buffer: onePixelPng,
  });
  await page.getByRole("button", { name: "开始识别" }).click();

  await expect(page.getByRole("heading", { name: "草稿编辑" })).toBeVisible();
  await page.getByLabel("商品中文名").fill("确认宠物凉感垫");
  await page.getByLabel("类目").fill("Pet supplies");
  await page.getByLabel("价格 CNY").fill("49.90");

  await page.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByRole("button", { name: "保存修改" })).toBeEnabled();
  await expect(page.getByLabel("商品中文名")).toHaveValue("确认宠物凉感垫");

  await page.getByRole("button", { name: "确认入库" }).click();

  await expect(page).toHaveURL(/\/products\?company_id=1&product_id=501$/);
  await expect(page.getByRole("heading", { name: "产品 / Products" })).toBeVisible();
  await expect(page.getByRole("row", { name: /确认宠物凉感垫.*Imported Pet Cooling Mat/ })).toBeVisible();
  await expect(page.getByRole("definition").filter({ hasText: "Imported Pet Cooling Mat" })).toBeVisible();
  await expect(page.getByText("该产品来自用户上传截图/链接，经 AI 提取后由用户确认。")).toBeVisible();
});

async function mockProductIntakeApi(page: Page): Promise<void> {
  const drafts = new Map<number, ProductDraftFixture>([
    [101, screenshotDraft()],
    [102, urlNeedsScreenshotDraft()],
  ]);
  let confirmedProduct: ProductFixture | null = null;

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (method === "GET" && path === "/api/companies") {
      await fulfillJson(route, { items: [demoCompany], total: 1 });
      return;
    }

    if (method === "POST" && path === "/api/product-intake/screenshot") {
      await fulfillJson(route, {
        import_job_id: 201,
        draft_id: 101,
        job_status: "draft_ready",
        draft_status: "draft",
        low_confidence: false,
        error_code: null,
        error_message: null,
        next_action: "review_draft",
        asset: {
          id: 301,
          file_name: "safe-upload.png",
          mime_type: "image/png",
          file_size: onePixelPng.length,
          width: 1,
          height: 1,
          created_at: "2026-05-29T00:00:00Z",
        },
        draft: draftSummary(drafts.get(101)),
      });
      return;
    }

    if (method === "POST" && path === "/api/product-intake/url") {
      await fulfillJson(route, {
        job_id: 202,
        draft_id: 102,
        status: "needs_screenshot",
        message: "请上传截图继续分析",
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
      const current = drafts.get(draftId) ?? screenshotDraft();
      const patch = (request.postDataJSON() ?? {}) as Partial<ProductDraftFixture>;
      const updated = {
        ...current,
        ...patch,
        selling_points: {
          ...(current?.selling_points ?? {}),
          ...(patch.selling_points ?? {}),
        },
        updated_at: "2026-05-29T01:00:00Z",
      } as ProductDraftFixture;
      drafts.set(draftId, updated);
      await fulfillJson(route, updated);
      return;
    }

    const confirmMatch = path.match(/^\/api\/product-intake\/drafts\/(\d+)\/confirm$/);
    if (confirmMatch && method === "POST") {
      const draft = drafts.get(Number(confirmMatch[1])) ?? screenshotDraft();
      confirmedProduct = productFromDraft(draft);
      drafts.set(draft.id, { ...draft, status: "confirmed", confirmed_product_id: confirmedProduct.id });
      await fulfillJson(route, confirmedProduct);
      return;
    }

    if (method === "GET" && path === "/api/products") {
      await fulfillJson(route, { items: confirmedProduct ? [confirmedProduct] : [], total: confirmedProduct ? 1 : 0 });
      return;
    }

    await fulfillJson(route, { detail: "Unhandled mock API route" }, 404);
  });
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function screenshotDraft(): ProductDraftFixture {
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
      risk_notes: ["截图信息需人工复核"],
    },
    target_users: ["pet owners"],
    source_platform: "taobao",
    evidence: [{ field: "product_name_cn", source: "screenshot_text", value: "宠物凉感垫" }],
    confidence_score: "0.8200",
    confirmed_product_id: null,
    low_confidence: false,
    created_at: "2026-05-29T00:00:00Z",
    updated_at: "2026-05-29T00:00:00Z",
  };
}

function urlNeedsScreenshotDraft(): ProductDraftFixture {
  return {
    ...screenshotDraft(),
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
    low_confidence: true,
  };
}

function draftSummary(draft: ProductDraftFixture | undefined): ProductDraftSummaryFixture {
  const source = draft ?? screenshotDraft();
  return {
    id: source.id,
    status: source.status,
    product_name_cn: source.product_name_cn,
    product_name_en: source.product_name_en,
    category: source.category,
    price_cny: source.price_cny,
    confidence_score: source.confidence_score,
    confirmed_product_id: source.confirmed_product_id,
    low_confidence: source.low_confidence,
  };
}

function productFromDraft(draft: ProductDraftFixture): ProductFixture {
  return {
    id: 501,
    company_id: draft.company_id,
    product_name_cn: draft.product_name_cn ?? "人工确认商品",
    product_name_en: draft.product_name_en,
    category: draft.category,
    cost_price_cny: draft.cost_price_cny,
    weight_kg: draft.weight_kg,
    package_size: draft.package_size,
    material: draft.material,
    certification: null,
    moq: null,
    description: "该产品来自用户上传截图/链接，经 AI 提取后由用户确认。参考价格仅为国内页面线索，非海外售价或采购成本。",
    created_at: "2026-05-29T01:00:00Z",
    updated_at: "2026-05-29T01:00:00Z",
  };
}

type ProductDraftSummaryFixture = {
  id: number;
  status: string;
  product_name_cn: string | null;
  product_name_en: string | null;
  category: string | null;
  price_cny: string | null;
  confidence_score: string | null;
  confirmed_product_id: number | null;
  low_confidence: boolean;
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
  evidence: Array<{ field: string; source: string; value: string | null }>;
  created_at: string;
  updated_at: string;
};

type ProductFixture = {
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
