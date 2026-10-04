export const LOCALES = ["en", "ar"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_STORAGE_KEY = "xpand.availability.locale";

export const isLocale = (value: unknown): value is Locale => (LOCALES as readonly unknown[]).includes(value);
export const directionOf = (locale: Locale): "ltr" | "rtl" => (locale === "ar" ? "rtl" : "ltr");

/** Intl locale tags. Arabic uses Jordan's calendar names (كانون الثاني, آب...) with Western digits 0-9. */
export const INTL_TAG: Record<Locale, string> = { en: "en-GB", ar: "ar-JO-u-nu-latn" };

/** Saved choice first, then the browser's language list, then English. */
export function detectLocale(saved: string | null | undefined, languages: readonly string[] | undefined): Locale {
  if (isLocale(saved)) return saved;
  for (const tag of languages ?? []) {
    const base = tag.toLowerCase().split("-")[0];
    if (isLocale(base)) return base;
  }
  return DEFAULT_LOCALE;
}

/** "/en/dashboard/?city=Amman" -> same page in `target`. Paths without a locale segment get one. */
export function switchLocalePath(pathname: string, target: Locale): string {
  const parts = pathname.split("/").filter(Boolean);
  if (isLocale(parts[0])) parts.shift();
  return `/${[target, ...parts].join("/")}/`;
}

export const withLocale = (locale: Locale, path: string): string => `/${locale}${path.startsWith("/") ? path : `/${path}`}`;
