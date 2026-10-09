"use client";

import { createContext, useContext, useMemo } from "react";
import { directionOf, withLocale, type Locale } from "./config";
import { formatDate, formatDateTime, formatJod, formatNumber, formatPct } from "./format";
import { labelFor, packLabel, type GlossaryField } from "./glossary";
import { MESSAGES, type Messages } from "./messages";

export interface I18n {
  locale: Locale;
  dir: "ltr" | "rtl";
  t: Messages;
  date: (iso: string | null | undefined, style?: "medium" | "short") => string;
  dateTime: (iso: string | null | undefined) => string;
  number: (value: number) => string;
  pct: (value: number) => string;
  jod: (value: number) => string;
  /** Display name of a dataset value (store, city, product...) in the current language. */
  label: (field: GlossaryField, value: string) => string;
  pack: (value: string) => string;
  href: (path: string) => string;
}

export const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const value = useMemo<I18n>(() => ({
    locale,
    dir: directionOf(locale),
    t: MESSAGES[locale],
    date: (iso, style) => formatDate(locale, iso, style),
    dateTime: (iso) => formatDateTime(locale, iso),
    number: (n) => formatNumber(locale, n),
    pct: formatPct,
    jod: (n) => formatJod(locale, n),
    label: (field, v) => labelFor(locale, field, v),
    pack: (v) => packLabel(locale, v),
    href: (path) => withLocale(locale, path),
  }), [locale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
