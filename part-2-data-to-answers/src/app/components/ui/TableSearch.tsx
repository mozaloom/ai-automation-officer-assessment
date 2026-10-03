"use client";

import { Search } from "lucide-react";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function TableSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="relative w-full sm:w-56">
      <Search className="pointer-events-none absolute inset-y-0 start-2.5 my-auto h-3.5 w-3.5 text-text-light" aria-hidden="true" />
      <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={t.common.search} aria-label={t.common.searchTable} autoComplete="off" spellCheck={false}
        className="h-8 w-full rounded-md border border-[#d0d5dd] bg-white ps-8 pe-2 text-sm text-text-dark placeholder:text-text-light outline-none transition-colors hover:border-[#9aa3d6] focus-visible:border-brand-blue focus-visible:ring-4 focus-visible:ring-brand-blue/15" />
    </div>
  );
}
