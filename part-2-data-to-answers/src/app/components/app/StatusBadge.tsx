"use client";

import { STATUS_COLORS } from "@/lib/format";
import type { StockStatus } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

/** A state is a coloured dot plus its name, so it never relies on colour alone. */
export default function StatusBadge({ status }: { status: StockStatus }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-text-dark">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: STATUS_COLORS[status] }} aria-hidden="true" />
      {t.status[status]}
    </span>
  );
}
