"use client";

import { useI18n } from "./LanguageProvider";

export function LanguageToggle() {
  const { locale, setLocale } = useI18n();
  const zhActive = locale === "zh-CN";

  return (
    <div
      aria-label="语言切换"
      className="inline-flex shrink-0 items-center rounded-md border border-slate-200 bg-white p-1 text-xs font-semibold shadow-sm"
    >
      <button
        aria-pressed={zhActive}
        className={`rounded px-2 py-1 transition ${zhActive ? "bg-river text-white" : "text-slate-600 hover:bg-slate-100"}`}
        type="button"
        onClick={() => setLocale("zh-CN")}
      >
        中
      </button>
      <span className="px-1 text-slate-300">/</span>
      <button
        aria-pressed={!zhActive}
        className={`rounded px-2 py-1 transition ${!zhActive ? "bg-river text-white" : "text-slate-600 hover:bg-slate-100"}`}
        type="button"
        onClick={() => setLocale("en")}
      >
        EN
      </button>
    </div>
  );
}
