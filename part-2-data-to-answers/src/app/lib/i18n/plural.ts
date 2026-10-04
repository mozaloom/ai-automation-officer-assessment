import { INTL_TAG, type Locale } from "./config";

export type PluralForms = Partial<Record<Intl.LDMLPluralRule, string>> & { other: string };

/** Picks the right word form for `count` ("1 store", "3 stores"; Arabic has six forms). */
export function plural(locale: Locale, count: number, forms: PluralForms): string {
  const rule = new Intl.PluralRules(INTL_TAG[locale]).select(count);
  return forms[rule] ?? forms.other;
}
