import data from "./glossary.json";
import type { Locale } from "./config";

type Entry = { ar: string; aliases?: string[] };
const glossary = data as unknown as Record<string, Record<string, Entry>>;

export type GlossaryField = "city" | "area" | "store_name" | "product_name" | "category" | "store_type" | "region" | "status";

/** Display name of a dataset value in the current language. Unknown values show as they are. */
export function labelFor(locale: Locale, field: GlossaryField, value: string): string {
  return locale === "ar" ? glossary[field]?.[value]?.ar ?? value : value;
}

/** "1.5 L" -> "1.5 لتر" in Arabic; English keeps the dataset's own form. */
export function packLabel(locale: Locale, pack: string): string {
  if (locale !== "ar") return pack;
  const match = /^(\d+(?:\.\d+)?)\s*(\w+)$/.exec(pack.trim());
  const unit = match ? glossary.unit?.[match[2]]?.ar : undefined;
  return match && unit ? `${match[1]} ${unit}` : pack;
}

export const glossaryData = glossary;
