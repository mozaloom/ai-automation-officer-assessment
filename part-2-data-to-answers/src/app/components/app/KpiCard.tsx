import Card from "@/components/ui/Card";
import type { LucideIcon } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string | number;
  hint?: string;
  accent?: "blue" | "purple" | "green" | "amber" | "red";
  icon?: LucideIcon;
}

const accentMap = {
  blue: { text: "text-brand-blue", iconBg: "bg-blue-50", iconText: "text-blue-500" },
  purple: { text: "text-brand-purple", iconBg: "bg-purple-50", iconText: "text-purple-500" },
  green: { text: "text-emerald-600", iconBg: "bg-emerald-50", iconText: "text-emerald-500" },
  amber: { text: "text-amber-600", iconBg: "bg-amber-50", iconText: "text-amber-500" },
  red: { text: "text-red-500", iconBg: "bg-red-50", iconText: "text-red-500" },
} as const;

export default function KpiCard({ label, value, hint, accent = "blue", icon: Icon }: KpiCardProps) {
  const a = accentMap[accent];
  return (
    <Card padding="md" hover>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-gray">{label}</p>
          <p className={`mt-2 text-3xl font-bold ${a.text}`} data-testid={`kpi-${label.toLowerCase().replace(/\W+/g, "-")}`}>{value}</p>
          {hint && <p className="mt-1 text-xs text-text-gray">{hint}</p>}
        </div>
        {Icon && <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl ${a.iconBg}`}><Icon className={`h-5 w-5 ${a.iconText}`} aria-hidden="true" /></div>}
      </div>
    </Card>
  );
}
