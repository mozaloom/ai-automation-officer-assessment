"use client";

import type { ActionType, MessageStatus } from "@/lib/api/inbox";
import { useI18n } from "@/lib/i18n/I18nProvider";

const DOT: Record<MessageStatus, string> = { PROCESSING: "#2D368F", EXECUTING: "#2D368F", PENDING_REVIEW: "#F59E0B", EXECUTED: "#10B981", IGNORED: "#9CA3AF", REJECTED: "#9CA3AF", FAILED: "#EF4444" };

/** State as a coloured dot plus its name, so it never relies on colour alone. */
export function StatusChip({ status }: { status: MessageStatus }) {
  const { t } = useI18n();
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-medium text-text-dark">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: DOT[status] }} aria-hidden="true" />{t.inbox.status[status]}
    </span>
  );
}

export function ActionChip({ action }: { action: ActionType | null }) {
  const { t } = useI18n();
  if (!action) return null;
  return <span className="inline-flex items-center rounded-full border border-line px-2 py-0.5 text-xs text-text-gray">{t.inbox.action[action]}</span>;
}
