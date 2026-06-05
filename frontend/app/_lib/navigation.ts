export type NavigationItem = {
  href: string;
  labelZh: string;
  labelEn: string;
};

export const navigationItems: NavigationItem[] = [
  { href: "/companies", labelZh: "企业", labelEn: "Companies" },
  { href: "/products", labelZh: "产品", labelEn: "Products" },
  { href: "/products/import", labelZh: "智能导入", labelEn: "Smart Intake" },
  { href: "/analysis/run", labelZh: "分析", labelEn: "Analysis" },
  { href: "/dashboard", labelZh: "看板", labelEn: "Dashboard" },
  { href: "/reports", labelZh: "报告", labelEn: "Reports" },
  { href: "/chat", labelZh: "聊天", labelEn: "Chat" },
];

export const utilityNavigationItems: NavigationItem[] = [
  { href: "/marketing", labelZh: "营销", labelEn: "Marketing" },
  { href: "/admin/api-keys", labelZh: "能力状态", labelEn: "AI Status" },
  { href: "/admin/data-sources", labelZh: "数据源", labelEn: "Data Sources" },
];
