import type { ChatContextIds, ChatPageContext } from "./api-client";
import type { Locale } from "./i18n";

export type ChatAssistantRole =
  | "general_assistant"
  | "data_analyst"
  | "business_advisor"
  | "market_researcher"
  | "report_reviewer";

export type ChatAssistantRoleOption = {
  id: ChatAssistantRole;
  labelZh: string;
  labelEn: string;
  shortZh: string;
  shortEn: string;
};

export type SafeChatRouteContext = {
  page: string;
  pathnameGroup: string;
  currentPage: string;
  contextIds: ChatContextIds;
};

type QueryReader = {
  get: (name: string) => string | null;
};

export const chatAssistantRoles: ChatAssistantRoleOption[] = [
  {
    id: "general_assistant",
    labelZh: "综合助手",
    labelEn: "General Assistant",
    shortZh: "综合",
    shortEn: "General",
  },
  {
    id: "data_analyst",
    labelZh: "数据分析师",
    labelEn: "Data Analyst",
    shortZh: "数据",
    shortEn: "Data",
  },
  {
    id: "business_advisor",
    labelZh: "企业服务顾问",
    labelEn: "Business Advisor",
    shortZh: "顾问",
    shortEn: "Advisor",
  },
  {
    id: "market_researcher",
    labelZh: "市场研究员",
    labelEn: "Market Researcher",
    shortZh: "市场",
    shortEn: "Market",
  },
  {
    id: "report_reviewer",
    labelZh: "报告质检员",
    labelEn: "Report Reviewer",
    shortZh: "质检",
    shortEn: "QC",
  },
];

export function deriveSafeChatRouteContext(pathname: string, searchParams: QueryReader): SafeChatRouteContext {
  const segments = pathname.split("/").filter(Boolean);
  const contextIds: ChatContextIds = {};
  const pathnameGroup = groupPathname(segments);
  const page = pageName(segments);

  if (segments[0] === "reports" && segments[1]) {
    const reportId = positiveInt(segments[1]);
    if (reportId) {
      contextIds.report_id = reportId;
    }
  }

  if (segments[0] === "dashboard" && segments[1]) {
    const analysisId = positiveInt(segments[1]);
    if (analysisId) {
      contextIds.analysis_id = analysisId;
    }
  }

  applyQueryId(searchParams, "company_id", contextIds);
  applyQueryId(searchParams, "product_id", contextIds);
  applyQueryId(searchParams, "analysis_id", contextIds);
  applyQueryId(searchParams, "report_id", contextIds);

  return {
    page,
    pathnameGroup,
    currentPage: pathnameGroup,
    contextIds,
  };
}

export function buildChatPageContext(
  routeContext: SafeChatRouteContext,
  locale: Locale,
  role: ChatAssistantRoleOption,
): ChatPageContext {
  return {
    page: routeContext.page,
    pathname_group: routeContext.pathnameGroup,
    locale,
    assistant_role: role.id,
    assistant_role_label: locale === "en" ? role.labelEn : role.labelZh,
    context_ids: routeContext.contextIds,
  };
}

export function chatSessionTitle(routeContext: SafeChatRouteContext): string {
  if (routeContext.contextIds.report_id) {
    return `Report chat #${routeContext.contextIds.report_id}`;
  }
  if (routeContext.contextIds.analysis_id) {
    return `Analysis chat #${routeContext.contextIds.analysis_id}`;
  }
  if (routeContext.contextIds.product_id) {
    return `Product chat #${routeContext.contextIds.product_id}`;
  }
  return `${routeContext.pathnameGroup} chat`;
}

export function roleById(roleId: ChatAssistantRole): ChatAssistantRoleOption {
  return chatAssistantRoles.find((role) => role.id === roleId) ?? chatAssistantRoles[0];
}

function groupPathname(segments: string[]): string {
  if (segments.length === 0) {
    return "home";
  }
  if (segments[0] === "reports" && segments[1]) {
    return "reports/detail";
  }
  if (segments[0] === "dashboard" && segments[1]) {
    return "dashboard/detail";
  }
  return segments.slice(0, 2).join("/");
}

function pageName(segments: string[]): string {
  if (segments.length === 0) {
    return "home";
  }
  if (segments[0] === "reports" && segments[1]) {
    return "report_detail";
  }
  if (segments[0] === "dashboard" && segments[1]) {
    return "dashboard_detail";
  }
  return segments.join("_").replace(/[^a-z0-9_/-]/gi, "_");
}

function applyQueryId(searchParams: QueryReader, key: keyof ChatContextIds, contextIds: ChatContextIds) {
  const parsed = positiveInt(searchParams.get(key));
  if (parsed) {
    contextIds[key] = parsed;
  }
}

function positiveInt(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}
