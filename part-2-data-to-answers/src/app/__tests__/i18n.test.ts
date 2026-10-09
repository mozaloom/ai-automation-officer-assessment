import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DEFAULT_LOCALE, detectLocale, directionOf, isLocale, switchLocalePath, withLocale } from "@/lib/i18n/config";
import { formatDate, formatJod, formatNumber, formatPct } from "@/lib/i18n/format";
import { glossaryData, labelFor, packLabel } from "@/lib/i18n/glossary";
import { MESSAGES } from "@/lib/i18n/messages";
import { plural } from "@/lib/i18n/plural";

const REPO = path.resolve(__dirname, "../../..");

/** Every key path, with function arity, so a missing or extra translation is a test failure. */
function shape(value: unknown, prefix = ""): string[] {
  if (typeof value === "function") return [`${prefix}()${value.length}`];
  if (Array.isArray(value)) return [`${prefix}[${value.length}]`];
  if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => shape(v, `${prefix}.${k}`));
  return [prefix];
}
const strings = (value: unknown): string[] =>
  typeof value === "string" ? [value] : Array.isArray(value) ? value.flatMap(strings) : value && typeof value === "object" ? Object.values(value).flatMap(strings) : [];

describe("dictionaries", () => {
  it("English and Arabic have exactly the same keys, function signatures and list lengths", () => {
    expect(shape(MESSAGES.ar).sort()).toEqual(shape(MESSAGES.en).sort());
  });
  it("no message is empty", () => {
    for (const locale of ["en", "ar"] as const) expect(strings(MESSAGES[locale]).filter((s) => !s.trim())).toEqual([]);
  });
  it("Arabic copy uses Western digits and no Latin leftovers except the brand and the email example", () => {
    const text = strings(MESSAGES.ar).join(" ");
    expect(text).not.toMatch(/[\u0660-\u0669]/);
    const latin = (text.match(/[A-Za-z]+/g) ?? []).filter((w) => !["XPAND", "name", "xpandpros", "com", "English", "ClickUp"].includes(w));
    expect(latin).toEqual([]);
  });
  it("Arabic states and the glossary agree, so tables and answers use the same words", () => {
    for (const [english, arabic] of Object.entries(MESSAGES.ar.status)) expect(glossaryData.status[english].ar).toBe(arabic);
  });
  it("Arabic sample questions are in Arabic and under the 500 character limit", () => {
    for (const q of MESSAGES.ar.assistant.samples) { expect(q).toMatch(/[\u0600-\u06FF]/); expect(q.length).toBeLessThanOrEqual(500); }
  });
});

describe("glossary", () => {
  const rows = readFileSync(path.join(REPO, "data/pos_availability.csv"), "utf8").trim().split(/\r?\n/);
  const header = rows[0].split(",");
  const column = (name: string) => [...new Set(rows.slice(1).map((l) => l.split(",")[header.indexOf(name)]))];

  it.each(["city", "area", "store_name", "product_name", "category", "store_type", "region"] as const)("has an Arabic name for every %s in the data", (field) => {
    expect(column(field).filter((v) => labelFor("ar", field, v) === v)).toEqual([]);
  });
  it("is the same file the backend uses (no drift)", () => {
    const source = readFileSync(path.join(REPO, "src/tools/glossary.json"), "utf8");
    expect(glossaryData).toEqual(JSON.parse(source));
  });
  it("keeps English values as they are and unknown values unchanged", () => {
    expect(labelFor("en", "city", "Amman")).toBe("Amman");
    expect(labelFor("ar", "city", "Atlantis")).toBe("Atlantis");
    expect(labelFor("ar", "city", "Amman")).toBe("عمّان");
  });
  it("writes pack sizes with Arabic units", () => {
    expect(packLabel("ar", "1.5 L")).toBe("1.5 لتر");
    expect(packLabel("ar", "5 kg")).toBe("5 كغم");
    expect(packLabel("ar", "100 bags")).toBe("100 كيس");
    expect(packLabel("en", "5 kg")).toBe("5 kg");
    expect(packLabel("ar", "odd pack")).toBe("odd pack");
  });
});

describe("formatting", () => {
  it("formats dates with Jordanian month names and Western digits", () => {
    expect(formatDate("ar", "2026-08-25")).toBe("25 آب 2026");
    expect(formatDate("ar", "2026-01-05")).toBe("5 كانون الثاني 2026");
    expect(formatDate("ar", "2026-12-01")).toBe("1 كانون الأول 2026");
    expect(formatDate("en", "2026-08-25")).toBe("25 Aug 2026");
    expect(formatDate("en", "2026-08-12", "short")).toBe("12 Aug");
    expect(formatDate("ar", "2026-08-12", "short")).toBe("12 آب");
  });
  it("passes through unparseable dates", () => { expect(formatDate("en", "soon")).toBe("soon"); expect(formatDate("ar", undefined)).toBe(""); });
  it("formats numbers with Western digits in both languages", () => {
    expect(formatNumber("en", 1234)).toBe("1,234");
    expect(formatNumber("ar", 1234567)).toMatch(/^1.234.567$/);
    expect(formatNumber("ar", 936)).toBe("936");
    expect(formatPct(63.55)).toMatch(/^63\.[56]%$/);
  });
  it("writes prices the way each language says them", () => {
    expect(formatJod("en", 6.9)).toBe("JOD 6.90");
    expect(formatJod("ar", 6.9)).toBe("6.90 دينار");
  });
});

describe("plural forms", () => {
  const forms = { one: "one", two: "two", few: "few", many: "many", other: "other" };
  it.each([[0, "other"], [1, "one"], [2, "two"], [3, "few"], [10, "few"], [11, "many"], [99, "many"], [100, "other"]])("Arabic %i -> %s", (n, form) => expect(plural("ar", n, forms)).toBe(form));
  it("English has one and other, and falls back to other", () => {
    expect(plural("en", 1, { one: "store", other: "stores" })).toBe("store");
    expect(plural("en", 5, { one: "store", other: "stores" })).toBe("stores");
    expect(plural("en", 2, { one: "x", other: "y" })).toBe("y");
  });
  it("writes the dashboard counts correctly in Arabic", () => {
    expect(MESSAGES.ar.dashboard.kpi.scope(40, 27, 12)).toBe("40 متجرًا، 27 منتجًا، 12 مدينة");
    expect(MESSAGES.ar.dashboard.kpi.scope(1, 2, 3)).toBe("متجر واحد، منتجان، 3 مدن");
    expect(MESSAGES.en.dashboard.kpi.scope(1, 27, 12)).toBe("1 store, 27 products, 12 cities");
  });
});

describe("locale routing helpers", () => {
  it("recognises locales and directions", () => {
    expect(isLocale("ar") && isLocale("en") && !isLocale("fr") && !isLocale(undefined)).toBe(true);
    expect([directionOf("ar"), directionOf("en")]).toEqual(["rtl", "ltr"]);
  });
  it("opens in the saved language, else the browser's first supported language, else English", () => {
    expect(detectLocale("ar", ["en-US"])).toBe("ar");
    expect(detectLocale(null, ["fr-FR", "ar-JO", "en"])).toBe("ar");
    expect(detectLocale(null, ["en-GB"])).toBe("en");
    expect(detectLocale("xx", ["de"])).toBe(DEFAULT_LOCALE);
    expect(detectLocale(undefined, undefined)).toBe(DEFAULT_LOCALE);
  });
  it("switches the language and keeps the page", () => {
    expect(switchLocalePath("/en/dashboard/", "ar")).toBe("/ar/dashboard/");
    expect(switchLocalePath("/ar/", "en")).toBe("/en/");
    expect(switchLocalePath("/dashboard/", "ar")).toBe("/ar/dashboard/");
    expect(withLocale("ar", "/login/")).toBe("/ar/login/");
    expect(withLocale("en", "login/")).toBe("/en/login/");
  });
});
