"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Suspense, useState } from "react";
import { navigationItems, utilityNavigationItems } from "../_lib/navigation";
import { FloatingChatWidget } from "./FloatingChatWidget";
import { LanguageToggle } from "./LanguageToggle";
import { useI18n } from "./LanguageProvider";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const { text } = useI18n();
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-start lg:justify-between lg:px-8">
          <Link href="/" className="group flex min-w-0 items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-river text-sm font-bold text-white shadow-panel">
              苏
            </span>
            <span className="min-w-0">
              <span className="block truncate text-lg font-semibold text-ink">
                {text("苏品智航", "Jiangsu ExportPilot")}
              </span>
              <span className="block truncate text-sm text-slate-500">
                {text(
                  "面向江苏制造企业出海的 AI 选品与海外市场洞察智能体",
                  "AI product selection and overseas market insights for Jiangsu manufacturers",
                )}
              </span>
            </span>
          </Link>
          <div className="grid min-w-0 gap-2 lg:justify-items-end">
            <div className="flex min-w-0 items-center gap-3">
              <nav
                aria-label={text("主导航", "Primary navigation")}
                className="-mx-1 flex min-w-0 max-w-full gap-1 overflow-x-auto px-1 pb-1"
              >
                {navigationItems.map((item) => {
                  const isActive =
                    item.href === "/products"
                      ? pathname === "/products"
                      : pathname === item.href || pathname.startsWith(`${item.href}/`);

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`shrink-0 rounded-md px-2.5 py-2 text-sm font-medium transition sm:px-3 ${
                        isActive
                          ? "bg-river text-white shadow-sm"
                          : "text-slate-600 hover:bg-slate-100 hover:text-ink"
                      }`}
                    >
                      {text(item.labelZh, item.labelEn)}
                    </Link>
                  );
                })}
              </nav>
              <LanguageToggle />
            </div>
            <nav aria-label={text("辅助导航", "Utility navigation")} className="flex flex-wrap gap-2 text-xs font-medium text-slate-500">
              {utilityNavigationItems.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={isActive ? "text-river" : "transition hover:text-ink"}
                  >
                    {text(item.labelZh, item.labelEn)}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      </header>
      <main
        className={`mx-auto w-full max-w-7xl px-4 py-8 transition-[padding] duration-200 sm:px-6 lg:px-8 ${
          chatOpen ? "lg:pr-[28rem]" : ""
        }`}
      >
        {children}
      </main>
      <Suspense fallback={null}>
        <FloatingChatWidget onOpenChange={setChatOpen} />
      </Suspense>
    </div>
  );
}
