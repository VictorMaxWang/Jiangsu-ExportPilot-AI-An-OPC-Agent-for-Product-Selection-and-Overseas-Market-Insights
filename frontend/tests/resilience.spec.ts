import { expect, Page, Route, test } from "@playwright/test";

test("admin provider status recovers from runtime 401 with password prompt", async ({ page }) => {
  let statusRequests = 0;
  let authorizedStatusRequests = 0;

  await page.route("**/api/admin/providers/status", async (route) => {
    statusRequests += 1;
    const password = route.request().headers()["x-admin-password"];
    if (!password) {
      await fulfillJson(route, { detail: "Unauthorized" }, 401);
      return;
    }
    expect(password).toBe("admin-secret");
    authorizedStatusRequests += 1;
    await fulfillJson(route, {
      providers: [
        {
          provider: "bailian",
          display_name: "Bailian Provider",
          status: "configured",
          mvp_priority: "P0",
          default_enabled: true,
          fallback: null,
          notes: "Configured by backend environment.",
        },
      ],
    });
  });

  await page.goto("/admin/api-keys");

  const passwordInput = page.locator('input[type="password"]');
  await expect(passwordInput).toBeVisible();
  await passwordInput.fill("admin-secret");
  await passwordInput.press("Enter");

  await expect(page.getByText("Bailian Provider")).toBeVisible();
  expect(statusRequests).toBeGreaterThanOrEqual(2);
  expect(authorizedStatusRequests).toBeGreaterThanOrEqual(1);
});

test("dashboard detail keeps loading state when an aborted stale request settles", async ({ page }) => {
  const dashboardTwo = createDeferred();

  await mockDashboardApi(page, {
    async beforeDashboardResponse(analysisId) {
      if (analysisId === 1) {
        await delay(500);
      }
      if (analysisId === 2) {
        await dashboardTwo.promise;
      }
    },
  });

  await page.goto("/dashboard/1");
  await page.goto("/dashboard/2");
  await page.waitForTimeout(150);

  await expect(page.getByRole("status")).toBeVisible();
  await expect(page.getByText("Dashboard Product 1")).toHaveCount(0);

  dashboardTwo.resolve();
  await expect(page.getByText("Dashboard Product 2").first()).toBeVisible();
});

test("report detail keeps loading state when an aborted stale request settles", async ({ page }) => {
  const reportTwo = createDeferred();

  await mockReportApi(page, {
    async beforeReportResponse(reportId) {
      if (reportId === 1) {
        await delay(500);
      }
      if (reportId === 2) {
        await reportTwo.promise;
      }
    },
  });

  await page.goto("/reports/1");
  await page.goto("/reports/2");
  await page.waitForTimeout(150);

  await expect(page.getByRole("status")).toBeVisible();
  await expect(page.getByText("Report Title 1")).toHaveCount(0);

  reportTwo.resolve();
  await expect(page.getByRole("heading", { name: "Report Title 2" })).toBeVisible();
});

test("language provider renders when localStorage access throws", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new DOMException("localStorage blocked", "SecurityError");
      },
    });
  });

  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
  await page.waitForTimeout(200);

  expect(pageErrors).toEqual([]);
});

type DashboardMockOptions = {
  beforeDashboardResponse?: (analysisId: number) => Promise<void>;
};

async function mockDashboardApi(page: Page, options: DashboardMockOptions = {}): Promise<void> {
  await page.route("**/api/dashboard/*", async (route) => {
    const analysisId = Number(new URL(route.request().url()).pathname.split("/").pop());
    await options.beforeDashboardResponse?.(analysisId);
    await fulfillJson(route, dashboardFixture(analysisId));
  });
}

type ReportMockOptions = {
  beforeReportResponse?: (reportId: number) => Promise<void>;
};

async function mockReportApi(page: Page, options: ReportMockOptions = {}): Promise<void> {
  await page.route("**/api/reports/*", async (route) => {
    const requestUrl = new URL(route.request().url());
    const segments = requestUrl.pathname.split("/").filter(Boolean);
    const reportId = Number(segments[2]);

    if (segments.length === 3) {
      await options.beforeReportResponse?.(reportId);
      await fulfillJson(route, reportFixture(reportId));
      return;
    }

    if (segments.length === 4 && segments[3] === "versions") {
      await fulfillJson(route, {
        items: [reportVersionFixture(reportId)],
        total: 1,
        current_version_id: reportId * 10,
      });
      return;
    }

    await route.fallback();
  });

  await mockDashboardApi(page);
}

function dashboardFixture(analysisId: number) {
  return {
    analysis_id: analysisId,
    product_scores: [
      {
        product_id: analysisId,
        product_name_cn: `Dashboard Product ${analysisId}`,
        product_name_en: `Dashboard Product ${analysisId}`,
        country: "US",
        keyword: "dashboard product",
        rank: 1,
        total_score: 88,
        trend_score: 85,
        price_score: 80,
        market_score: 90,
        supply_score: 86,
        logistics_score: 82,
        content_score: 84,
        fallback_used: false,
        ai_fallback_used: false,
      },
    ],
    country_scores: [
      {
        country: "US",
        average_score: 88,
        top_score: 88,
        recommendation_count: 1,
        top_product_id: analysisId,
        top_product_name: `Dashboard Product ${analysisId}`,
      },
    ],
    price_ranges: [
      {
        product_id: analysisId,
        product_name: `Dashboard Product ${analysisId}`,
        country: "US",
        keyword: "dashboard product",
        min_price: 10,
        median_price: 15,
        avg_price: 16,
        max_price: 20,
        currency: "USD",
        item_count: 5,
        competition_level: "medium",
        price_suggestion: null,
        sample_notice: "sample",
      },
    ],
    content_themes: [],
    top_recommendations: [
      {
        rank: 1,
        product_id: analysisId,
        product_name: `Dashboard Product ${analysisId}`,
        country: "US",
        total_score: 88,
        reason: "Strong demo fit.",
        next_action: "Review landed cost.",
        fallback_used: false,
        ai_fallback_used: false,
      },
    ],
    risk_cards: [],
    data_sources_used: [
      {
        provider: "fixture",
        label: "Fixture source",
        source_type: "sample",
        fallback_used: false,
        api_invoked: false,
        detail: null,
      },
    ],
  };
}

function reportFixture(reportId: number) {
  return {
    id: reportId,
    analysis_id: reportId,
    company_id: 1,
    title: `Report Title ${reportId}`,
    content_markdown: `# Report Title ${reportId}`,
    content_html: null,
    pdf_url: null,
    current_version_id: reportId * 10,
    created_at: "2026-06-28T00:00:00Z",
    updated_at: "2026-06-28T00:00:00Z",
  };
}

function reportVersionFixture(reportId: number) {
  return {
    id: reportId * 10,
    report_id: reportId,
    version_number: 1,
    parent_version_id: null,
    content_markdown: `# Report Title ${reportId}`,
    content_html: null,
    source_type: "generated",
    source_proposal_id: null,
    created_by: "system",
    version_note: "Fixture version",
    created_at: "2026-06-28T00:00:00Z",
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function createDeferred(): { promise: Promise<void>; resolve: () => void } {
  let resolvePromise: (() => void) | undefined;
  const promise = new Promise<void>((resolve) => {
    resolvePromise = resolve;
  });
  return {
    promise,
    resolve: () => resolvePromise?.(),
  };
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}
