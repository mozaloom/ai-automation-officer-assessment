"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import SortHeader from "@/components/ui/SortHeader";
import TableSearch from "@/components/ui/TableSearch";
import { describeError } from "@/lib/api/errors";
import { fetchActivity, fetchMessages } from "@/lib/api/inbox";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useTable } from "@/lib/table";

export default function ActivityView() {
  const { t, dateTime, locale } = useI18n();
  const a = t.inbox.activity;
  const activity = useQuery({ queryKey: ["inbox", "activity"], queryFn: fetchActivity, refetchInterval: 10_000 });
  const messages = useQuery({ queryKey: ["inbox", "messages"], queryFn: fetchMessages });
  const subjects = new Map((messages.data?.messages ?? []).map((m) => [m.message_id, m.subject]));
  const eventName = (e: string) => a.events[e as keyof typeof a.events] ?? e;
  const rows = activity.data?.events ?? [];
  const table = useTable(rows, { time: (r) => r.at, event: (r) => eventName(r.event), actor: (r) => r.actor, action: (r) => r.action ?? "", outcome: (r) => r.outcome ?? "" },
    (r) => `${eventName(r.event)} ${r.actor} ${r.action ?? ""} ${r.outcome ?? ""} ${r.detail ?? ""} ${subjects.get(r.message_id) ?? ""}`, locale);
  const h = (key: string, text: string, cls = "") => <SortHeader label={text} active={table.sortKey === key} dir={table.dir} onSort={() => table.toggle(key)} className={`pe-3 ${cls}`} />;
  return (
    <div className="space-y-5">
      <header><h1 className="text-2xl font-bold tracking-tight text-text-dark">{a.title}</h1><p className="mt-1 text-sm text-text-gray">{a.subtitle}</p></header>
      {activity.isError && !activity.data ? (
        <EmptyState icon={<AlertTriangle className="h-6 w-6" aria-hidden="true" />} title={t.inbox.errors.loadFailed} body={describeError(activity.error, t)} action={<Button variant="outline" size="sm" onClick={() => activity.refetch()}>{t.dashboard.retry}</Button>} />
      ) : !activity.data ? <Skeleton className="h-72" /> : rows.length === 0 ? <EmptyState title={a.empty} /> : (
        <div>
          <div className="mb-2"><TableSearch value={table.query} onChange={table.setQuery} /></div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm" data-testid="activity-table">
              <thead><tr className="border-b border-line">{h("time", a.time)}{h("event", a.event)}{h("actor", a.actor)}{h("action", a.action)}{h("outcome", a.outcome)}<th scope="col" className="py-2 pe-3 text-start text-xs font-medium text-text-gray">{a.email}</th><th scope="col" className="py-2 text-start text-xs font-medium text-text-gray">{a.task}</th></tr></thead>
              <tbody className="divide-y divide-line">
                {table.rows.map((r) => (
                  <tr key={r.id} className="transition-colors hover:bg-wash">
                    <td className="whitespace-nowrap py-2 pe-3 text-xs tabular-nums text-text-gray">{dateTime(r.at)}</td>
                    <td className="py-2 pe-3 font-medium text-text-dark">{eventName(r.event)}</td>
                    <td className="max-w-[10rem] truncate py-2 pe-3 text-text-gray" dir="ltr" title={r.actor}>{r.actor}</td>
                    <td className="py-2 pe-3 text-text-gray">{r.action ? t.inbox.action[r.action as keyof typeof t.inbox.action] ?? r.action : ""}</td>
                    <td className="py-2 pe-3 text-text-gray">{r.outcome ?? ""}</td>
                    <td className="max-w-[16rem] truncate py-2 pe-3 text-text-dark" title={subjects.get(r.message_id)}>{subjects.get(r.message_id) ?? (r.detail && r.message_id === "-" ? r.detail : "")}</td>
                    <td className="py-2 text-xs text-text-gray" dir="ltr">{r.task_id ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {table.rows.length === 0 && <p className="py-6 text-center text-sm text-text-gray">{t.common.noRows}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
