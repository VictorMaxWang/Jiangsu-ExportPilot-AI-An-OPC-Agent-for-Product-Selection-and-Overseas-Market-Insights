export type NavigationItem = {
  href: string;
  labelZh: string;
  labelEn: string;
};

export const navigationItems: NavigationItem[] = [
  { href: "/", labelZh: "首页", labelEn: "Home" },
  { href: "/companies", labelZh: "企业", labelEn: "Companies" },
  { href: "/products", labelZh: "产品", labelEn: "Products" },
  { href: "/analysis/run", labelZh: "分析", labelEn: "Analysis" },
  { href: "/dashboard", labelZh: "看板", labelEn: "Dashboard" },
  { href: "/marketing", labelZh: "营销", labelEn: "Marketing" },
  { href: "/reports", labelZh: "报告", labelEn: "Reports" },
  { href: "/admin/api-keys", labelZh: "能力状态", labelEn: "AI Status" },
  { href: "/admin/data-sources", labelZh: "数据源", labelEn: "Data Sources" },
];
