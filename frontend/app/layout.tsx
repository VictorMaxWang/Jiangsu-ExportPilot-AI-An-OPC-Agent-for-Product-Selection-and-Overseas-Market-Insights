import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "./_components/AppShell";

export const metadata: Metadata = {
  title: "苏品智航 / Jiangsu ExportPilot",
  description: "面向江苏制造企业出海的 AI 选品与海外市场洞察智能体。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
