import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "./_components/AppShell";

export const metadata: Metadata = {
  title: "苏品智航 / Jiangsu ExportPilot",
  description: "AI product selection and overseas market insight platform for Jiangsu manufacturing companies.",
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
