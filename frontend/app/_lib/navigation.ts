export type NavigationItem = {
  href: string;
  label: string;
};

export const navigationItems: NavigationItem[] = [
  { href: "/", label: "Home" },
  { href: "/companies", label: "Companies" },
  { href: "/products", label: "Products" },
  { href: "/analysis/run", label: "Run Analysis" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/reports", label: "Reports" },
  { href: "/admin/api-keys", label: "API Keys" },
];
