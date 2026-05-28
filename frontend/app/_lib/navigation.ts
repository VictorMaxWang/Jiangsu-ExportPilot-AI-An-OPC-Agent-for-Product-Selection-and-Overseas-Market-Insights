export type NavigationItem = {
  href: string;
  label: string;
};

export const navigationItems: NavigationItem[] = [
  { href: "/", label: "首页" },
  { href: "/companies", label: "企业" },
  { href: "/products", label: "产品" },
  { href: "/analysis/run", label: "分析" },
  { href: "/dashboard", label: "看板" },
  { href: "/marketing", label: "营销" },
  { href: "/reports", label: "报告" },
  { href: "/admin/api-keys", label: "能力状态" },
  { href: "/admin/data-sources", label: "数据源" },
];
