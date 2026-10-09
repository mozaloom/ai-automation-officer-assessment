import { INTL_TAG, type Locale } from "./config";

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

/** "2026-08-25" -> "25 Aug 2026" / "25 آب 2026". Built from UTC parts so the time zone never shifts the day. */
export function formatDate(locale: Locale, iso: string | undefined | null, style: "medium" | "short" = "medium"): string {
  const match = ISO.exec(iso ?? "");
  if (!match) return iso ?? "";
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat(INTL_TAG[locale], {
    day: "numeric",
    month: style === "short" ? "short" : locale === "ar" ? "long" : "short",
    ...(style === "short" ? {} : { year: "numeric" }),
    timeZone: "UTC",
  }).format(date);
}

/** "2026-10-05T08:30:00.000Z" -> "5 Oct 2026, 11:30" in the viewer's time zone. */
export function formatDateTime(locale: Locale, iso: string | undefined | null): string {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return iso ?? "";
  return new Intl.DateTimeFormat(INTL_TAG[locale], { day: "numeric", month: locale === "ar" ? "long" : "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
}

export const formatNumber = (locale: Locale, value: number): string => new Intl.NumberFormat(INTL_TAG[locale]).format(value);
export const formatPct = (value: number): string => `${value.toFixed(1)}%`;

/** English "JOD 3.20"; Arabic "3.20 دينار" (the amount first, as it is written and said in Jordan). */
export function formatJod(locale: Locale, value: number): string {
  const amount = value.toFixed(2);
  return locale === "ar" ? `${amount} دينار` : `JOD ${amount}`;
}
