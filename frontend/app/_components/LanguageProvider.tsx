"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import type { Locale } from "../_lib/i18n";
import { defaultLocale, localeStorageKey, normalizeLocale, pickLocaleText } from "../_lib/i18n";

type LanguageContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  text: (zh: string, en?: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(defaultLocale);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setLocaleState(readStoredLocale());
    setHydrated(true);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    if (hydrated) {
      writeStoredLocale(locale);
    }
  }, [hydrated, locale]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      locale,
      setLocale: setLocaleState,
      toggleLocale: () => setLocaleState((current) => (current === "zh-CN" ? "en" : "zh-CN")),
      text: (zh, en) => pickLocaleText(locale, zh, en),
    }),
    [locale],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n(): LanguageContextValue {
  const value = useContext(LanguageContext);
  if (!value) {
    throw new Error("useI18n must be used within LanguageProvider");
  }
  return value;
}

export function LocalizedText({ zh, en }: { zh: string; en?: string }) {
  const { text } = useI18n();
  return <>{text(zh, en)}</>;
}

function readStoredLocale(): Locale {
  try {
    return normalizeLocale(window.localStorage.getItem(localeStorageKey));
  } catch {
    return defaultLocale;
  }
}

function writeStoredLocale(locale: Locale): void {
  try {
    window.localStorage.setItem(localeStorageKey, locale);
  } catch {
    // Some embedded browsers and privacy modes deny localStorage access.
  }
}
