"use client";

import { RotateCcw } from "lucide-react";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import type { DashboardFilters } from "@/lib/api/availability";
import type { DashboardData } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

interface Props {
  options?: DashboardData["options"];
  value: DashboardFilters;
  onChange: (next: DashboardFilters) => void;
}

export default function FilterBar({ options, value, onChange }: Props) {
  const { t, label } = useI18n();
  const active = Boolean(value.city || value.category || value.status);
  return (
    <div className="flex flex-wrap items-end gap-3" role="group" aria-label={t.dashboard.filtersLabel}>
      <div className="w-full sm:w-44">
        <Select label={t.dashboard.city} name="city" value={value.city ?? ""} onChange={(e) => onChange({ ...value, city: e.target.value || undefined })}
          options={(options?.cities ?? []).map((v) => ({ value: v, label: label("city", v) }))} emptyLabel={t.dashboard.allCities} />
      </div>
      <div className="w-full sm:w-44">
        <Select label={t.dashboard.category} name="category" value={value.category ?? ""} onChange={(e) => onChange({ ...value, category: e.target.value || undefined })}
          options={(options?.categories ?? []).map((v) => ({ value: v, label: label("category", v) }))} emptyLabel={t.dashboard.allCategories} />
      </div>
      <div className="w-full sm:w-44">
        <Select label={t.dashboard.stockStatus} name="status" value={value.status ?? ""} onChange={(e) => onChange({ ...value, status: e.target.value || undefined })}
          options={(options?.statuses ?? []).map((v) => ({ value: v, label: t.status[v] }))} emptyLabel={t.dashboard.allStates} />
      </div>
      {active && <Button variant="ghost" size="sm" onClick={() => onChange({})}><RotateCcw className="h-4 w-4" aria-hidden="true" />{t.dashboard.reset}</Button>}
    </div>
  );
}
