import type { PosRecord } from "@/lib/api/types";

export type GroupBy = "city" | "area" | "store_name" | "product_name" | "availability_status";
export type Measure = "count" | "quantity" | "avgPrice" | "minPrice";
export const GROUPS: GroupBy[] = ["city", "area", "store_name", "product_name", "availability_status"];
export const MEASURES: Measure[] = ["count", "quantity", "avgPrice", "minPrice"];

export interface ChartRow { key: string; value: number }

/** Groups records and measures each group. Sorted largest first (lowest-price charts sort smallest first, since cheap is the point). */
export function aggregate(records: PosRecord[], by: GroupBy, measure: Measure): ChartRow[] {
  const groups = new Map<string, PosRecord[]>();
  for (const r of records) groups.set(r[by], [...(groups.get(r[by]) ?? []), r]);
  const rows = [...groups].map(([key, rs]) => {
    const prices = rs.map((r) => r.shelf_price_jod);
    const value = measure === "count" ? rs.length : measure === "quantity" ? rs.reduce((s, r) => s + r.quantity_on_shelf, 0)
      : measure === "avgPrice" ? prices.reduce((a, b) => a + b, 0) / prices.length : Math.min(...prices);
    return { key, value: Math.round(value * 100) / 100 };
  });
  const cheapFirst = measure === "minPrice";
  return rows.sort((a, b) => (cheapFirst ? a.value - b.value : b.value - a.value) || a.key.localeCompare(b.key));
}

/** Questions that ask for a chart open the records as a chart straight away. */
export const wantsChart = (question: string): boolean => /\b(chart|graph|plot|visuali[sz]e|visuali[sz]ation|diagram)\b|مخطط|رسم بياني|رسم|بياني/i.test(question);
