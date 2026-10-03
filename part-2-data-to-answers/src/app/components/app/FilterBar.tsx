"use client";

import { RotateCcw } from "lucide-react";
import Select from "@/components/ui/Select";
import Button from "@/components/ui/Button";
import type { DashboardData } from "@/lib/api/types";
import type { DashboardFilters } from "@/lib/api/availability";

interface Props {
  options?: DashboardData["options"];
  value: DashboardFilters;
  onChange: (next: DashboardFilters) => void;
}

const toOptions = (values: string[] = []) => values.map((v) => ({ value: v, label: v }));

export default function FilterBar({ options, value, onChange }: Props) {
  const active = Boolean(value.city || value.category || value.status);
  return (
    <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_auto]" role="group" aria-label="Dashboard filters">
      <Select label="City" name="city" value={value.city ?? ""} onChange={(e) => onChange({ ...value, city: e.target.value || undefined })} options={toOptions(options?.cities)} emptyLabel="All cities" />
      <Select label="Category" name="category" value={value.category ?? ""} onChange={(e) => onChange({ ...value, category: e.target.value || undefined })} options={toOptions(options?.categories)} emptyLabel="All categories" />
      <Select label="Stock status" name="status" value={value.status ?? ""} onChange={(e) => onChange({ ...value, status: e.target.value || undefined })} options={toOptions(options?.statuses)} emptyLabel="All states" />
      <Button variant="pill-outline" size="sm" disabled={!active} onClick={() => onChange({})} className="h-[42px]"><RotateCcw className="h-4 w-4" aria-hidden="true" />Reset</Button>
    </div>
  );
}
