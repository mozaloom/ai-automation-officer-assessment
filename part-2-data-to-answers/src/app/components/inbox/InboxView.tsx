"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ExternalLink, RefreshCw, RotateCcw } from "lucide-react";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import { describeError } from "@/lib/api/errors";
import { fetchInboxConfig, fetchMessage, fetchMessages, retryItem, startSync, type MessageSummary } from "@/lib/api/inbox";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { ActionChip, StatusChip } from "./Chips";
import ModeBanner from "./ModeBanner";
import ProposalView from "./ProposalView";

export default function InboxView() {
  const { t, dateTime } = useI18n();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const config = useQuery({ queryKey: ["inbox", "config"], queryFn: fetchInboxConfig, staleTime: 60_000 });
  const list = useQuery({
    queryKey: ["inbox", "messages"], queryFn: fetchMessages,
    refetchInterval: (q) => (q.state.data?.sync?.state === "running" || q.state.data?.messages.some((m) => m.status === "PROCESSING" || m.status === "EXECUTING") ? 2500 : false),
  });
  const sync = useMutation({ mutationFn: startSync, onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox"] }) });
  const messages = list.data?.messages ?? [];
  const current = selected ?? messages[0]?.message_id ?? null;
  const detail = useQuery({ queryKey: ["inbox", "message", current], queryFn: () => fetchMessage(current!), enabled: current !== null, refetchInterval: (q) => (q.state.data && ["PROCESSING", "EXECUTING"].includes(q.state.data.status) ? 2500 : false) });
  const retry = useMutation({ mutationFn: (id: string) => retryItem(id), onSettled: () => qc.invalidateQueries({ queryKey: ["inbox"] }) });
  const s = list.data?.sync;
  const running = s?.state === "running" || sync.isPending;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-dark">{t.inbox.title}</h1>
          <p className="mt-1 text-sm text-text-gray">{t.inbox.subtitle}</p>
          <p className="mt-1 text-xs text-text-gray" dir="ltr">{t.inbox.mailbox}: {config.data?.mailbox ?? "…"}{config.data?.clickup_list_url && <> · <a href={config.data.clickup_list_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand-blue hover:underline">{t.inbox.clickupList}<ExternalLink className="h-3 w-3" aria-hidden="true" /></a></>}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Button onClick={() => sync.mutate()} loading={running} disabled={running}><RefreshCw className="h-4 w-4" aria-hidden="true" />{running ? t.inbox.sync.running : t.inbox.sync.button}</Button>
          <p className="text-xs text-text-gray" role="status" data-testid="sync-status">
            {sync.isError ? describeError(sync.error, t) : !s ? t.inbox.sync.never : s.state === "failed" ? `${t.inbox.sync.failed}${s.error ? ` (${s.error})` : ""}` : s.state === "running" ? t.inbox.sync.running : t.inbox.sync.done(s.fetched ?? 0, s.new ?? 0, s.duplicates ?? 0, s.failed ?? 0)}
          </p>
        </div>
      </header>

      <ModeBanner outlook={list.data?.mode.outlook} clickup={list.data?.mode.clickup} />

      {list.isError && !list.data ? (
        <EmptyState icon={<AlertTriangle className="h-6 w-6" aria-hidden="true" />} title={t.inbox.errors.loadFailed} body={describeError(list.error, t)} action={<Button variant="outline" size="sm" onClick={() => list.refetch()}>{t.dashboard.retry}</Button>} />
      ) : !list.data ? <Skeleton className="h-72" /> : messages.length === 0 ? (
        <EmptyState title={t.inbox.empty} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
          <ul className="max-h-[70dvh] divide-y divide-line overflow-auto rounded-xl border border-line" aria-label={t.inbox.title}>
            {messages.map((m: MessageSummary) => (
              <li key={m.message_id}>
                <button type="button" onClick={() => setSelected(m.message_id)} aria-current={m.message_id === current ? "true" : undefined}
                  className={`block w-full px-3 py-2.5 text-start transition-colors hover:bg-wash ${m.message_id === current ? "bg-brand-blue/[0.06]" : ""}`}>
                  <span className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium text-text-dark">{m.sender_name || m.sender}</span><span className="shrink-0 text-[11px] tabular-nums text-text-gray">{dateTime(m.received_at)}</span></span>
                  <span className="mt-0.5 block truncate text-sm text-text-dark">{m.subject}</span>
                  <span className="mt-1.5 flex flex-wrap items-center gap-2"><StatusChip status={m.status} /><ActionChip action={m.action} /></span>
                </button>
              </li>
            ))}
          </ul>
          <div className="min-w-0 rounded-xl border border-line p-4 sm:p-5">
            {!detail.data ? <Skeleton className="h-64" /> : (
              <>
                <ProposalView m={detail.data} />
                {detail.data.status === "FAILED" && detail.data.error && (
                  <div role="alert" className="mt-4 rounded-md border border-red-100 bg-red-50 px-3 py-2.5 text-sm text-red-800">
                    <p className="font-medium">{t.inbox.detail.error}: {detail.data.error.code}</p>
                    <p className="mt-0.5 text-xs">{detail.data.error.message}</p>
                    {detail.data.error.retryable ? <Button variant="outline" size="sm" className="mt-2" onClick={() => retry.mutate(detail.data!.message_id)} loading={retry.isPending}><RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />{t.inbox.detail.retry}</Button> : <p className="mt-1 text-xs">{t.inbox.detail.notRetryable}</p>}
                    {retry.isError && <p className="mt-1 text-xs">{describeError(retry.error, t)}</p>}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
