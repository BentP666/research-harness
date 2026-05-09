"use client";

/**
 * Lightweight i18n context — stores current locale, loads the JSON bundle,
 * exposes t(key, vars) and setLocale. Persists choice to localStorage.
 *
 * We use a custom provider instead of next-intl server-config because:
 * 1. Our UI is almost entirely client components (dev dashboards).
 * 2. Locale choice is per-user runtime setting, not per-URL-segment.
 * 3. Keeping it this thin lets us swap to next-intl later with zero breakage
 *    — call signatures (useT().t) match.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import enMessages from "@/locales/en.json";
import zhMessages from "@/locales/zh.json";
import { setLocale as setGlossaryLocale, type Locale } from "@/lib/glossary";

type Messages = typeof enMessages;

const BUNDLES: Record<Locale, Messages> = {
  en: enMessages as Messages,
  zh: zhMessages as Messages,
};

const STORAGE_KEY = "rh.locale";

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getClientLocale(): Locale {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "zh") return saved;
    const browserLang = window.navigator.language?.toLowerCase() ?? "";
    return browserLang.startsWith("zh") ? "zh" : "en";
  } catch {
    return "en";
  }
}

function getByPath(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, key) => {
    if (acc && typeof acc === "object" && key in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[key];
    }
    return undefined;
  }, obj);
}

function interpolate(
  raw: string,
  vars?: Record<string, string | number>
): string {
  if (!vars) return raw;
  return raw.replace(/\{(\w+)\}/g, (m, key) =>
    key in vars ? String(vars[key]) : m
  );
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Keep the first client render identical to SSR. Reading localStorage or
  // navigator.language during the initial render causes hydration mismatches
  // (for example server renders "Workbench" while client renders "工作台").
  const [locale, setLocaleState] = useState<Locale>("en");
  const [localeResolved, setLocaleResolved] = useState(false);

  useEffect(() => {
    const next = getClientLocale();
    window.queueMicrotask(() => {
      setLocaleState(next);
      setGlossaryLocale(next);
      setLocaleResolved(true);
    });
  }, []);

  useEffect(() => {
    if (!localeResolved) return;
    setGlossaryLocale(locale);
    try {
      window.localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      // localStorage blocked — keep in-memory locale
    }
  }, [locale, localeResolved]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleResolved(true);
    setLocaleState(next);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>): string => {
      const bundle = BUNDLES[locale];
      const val = getByPath(bundle, key);
      if (typeof val === "string") return interpolate(val, vars);
      // Fallback to English
      const fallback = getByPath(BUNDLES.en, key);
      if (typeof fallback === "string") return interpolate(fallback, vars);
      return key; // expose missing keys to surface gaps
    },
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useT(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // Safe fallback so deep components never crash during SSR / mounting race
    return {
      locale: "en",
      setLocale: () => {},
      t: (key) => {
        const val = getByPath(BUNDLES.en, key);
        return typeof val === "string" ? val : key;
      },
    };
  }
  return ctx;
}
