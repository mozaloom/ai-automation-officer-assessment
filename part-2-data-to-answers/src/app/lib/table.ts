import { useMemo, useState } from "react";

export type SortDir = "asc" | "desc";

/** Client-side sorting and searching for a table. Sorting is stable and compares numbers as numbers and text by locale. */
export function useTable<T>(rows: T[], sorters: Record<string, (row: T) => string | number>, haystack: (row: T) => string, locale: string) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [dir, setDir] = useState<SortDir>("desc");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let out = q ? rows.filter((r) => haystack(r).toLowerCase().includes(q)) : rows;
    const get = sortKey ? sorters[sortKey] : undefined;
    if (get) {
      const sign = dir === "asc" ? 1 : -1;
      out = [...out].sort((a, b) => {
        const x = get(a), y = get(b);
        return sign * (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), locale));
      });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sorters and haystack are stable per component
  }, [rows, query, sortKey, dir, locale]);

  const toggle = (key: string) => {
    if (sortKey === key) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setDir("desc"); }
  };
  return { rows: visible, sortKey, dir, toggle, query, setQuery };
}
