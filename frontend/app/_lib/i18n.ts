export type Locale = "zh-CN" | "en";

export const defaultLocale: Locale = "zh-CN";
export const localeStorageKey = "supinzhihang.locale";

export function normalizeLocale(value: string | null | undefined): Locale {
  return value === "en" ? "en" : defaultLocale;
}

export function pickLocaleText(locale: Locale, zh: string, en?: string): string {
  return locale === "en" && en ? en : zh;
}
