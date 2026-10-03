"use client";

import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { SortDir } from "@/lib/table";

/** A column header that sorts when clicked and tells assistive technology which way it is sorted. */
export default function SortHeader({ label, active, dir, onSort, className = "", align = "start" }: { label: string; active: boolean; dir: SortDir; onSort: () => void; className?: string; align?: "start" | "end" }) {
  const { t } = useI18n();
  const Icon = !active ? ChevronsUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th scope="col" aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"} className={`py-2 text-xs font-medium text-text-gray ${align === "end" ? "text-end" : "text-start"} ${className}`}>
      <button type="button" onClick={onSort} aria-label={t.common.sortBy(label)} className={`inline-flex items-center gap-1 rounded-sm transition-colors hover:text-text-dark ${align === "end" ? "flex-row-reverse" : ""}`}>
        {label}<Icon className={`h-3 w-3 ${active ? "text-brand-blue" : "opacity-50"}`} aria-hidden="true" />
      </button>
    </th>
  );
}
