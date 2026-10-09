"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Pencil, X } from "lucide-react";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import { describeError } from "@/lib/api/errors";
import { approveItem, fetchInboxConfig, fetchReview, rejectItem, type MessageDetail } from "@/lib/api/inbox";
import { ApiError } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";
import EditDialog from "./EditDialog";
import ModeBanner from "./ModeBanner";
import ProposalView from "./ProposalView";

function ReviewCard({ item, config }: { item: MessageDetail; config?: Parameters<typeof EditDialog>[0]["config"] }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const done = (message: string) => { setNotice(message); setEditing(false); setRejecting(false); void qc.invalidateQueries({ queryKey: ["inbox"] }); };
  const approve = useMutation({ mutationFn: () => approveItem(item.message_id), onSuccess: () => done(t.inbox.review.approved) });
  const reject = useMutation({ mutationFn: () => rejectItem(item.message_id, reason), onSuccess: () => done(t.inbox.review.rejected) });
  const error = approve.error ?? reject.error;
  const problems = error instanceof ApiError && Array.isArray((error.payload as { error?: { problems?: string[] } } | undefined)?.error?.problems) ? (error.payload as { error: { problems: string[] } }).error.problems : [];
  return (
    <article className="rounded-xl border border-line p-4 sm:p-5" aria-label={item.subject} data-testid="review-card">
      <ProposalView m={item} />
      {!item.can_approve && item.problems.length > 0 && (
        <p className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900"><span className="font-medium">{t.inbox.review.cannotApprove}</span> {item.problems.join("; ")}</p>
      )}
      {notice && <p role="status" className="mt-4 text-sm font-medium text-emerald-700">{notice}</p>}
      {error && <div role="alert" className="mt-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-800"><p>{describeError(error, t)}</p>{problems.length > 0 && <ul className="mt-1 list-disc ps-5 text-xs">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}</div>}
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
        <Button size="sm" onClick={() => approve.mutate()} loading={approve.isPending} disabled={!item.can_approve || reject.isPending}><Check className="h-4 w-4" aria-hidden="true" />{approve.isPending ? t.inbox.review.approving : t.inbox.review.approve}</Button>
        <Button size="sm" variant="outline" onClick={() => setEditing(true)} disabled={approve.isPending}><Pencil className="h-3.5 w-3.5" aria-hidden="true" />{t.inbox.review.edit}</Button>
        <Button size="sm" variant="outline" onClick={() => setRejecting((v) => !v)} disabled={approve.isPending}><X className="h-3.5 w-3.5" aria-hidden="true" />{t.inbox.review.reject}</Button>
      </div>
      {rejecting && (
        <form className="mt-3 space-y-2" onSubmit={(e) => { e.preventDefault(); reject.mutate(); }} aria-label={t.inbox.review.rejectTitle}>
          <label className="flex flex-col gap-1.5 text-sm font-medium">{t.inbox.review.rejectReason}<input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} className="h-10 rounded-md border border-[#d0d5dd] px-3 text-sm font-normal focus-visible:border-brand-blue focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-blue/15" /></label>
          <div className="flex gap-2"><Button type="submit" size="sm" loading={reject.isPending}>{t.inbox.review.confirmReject}</Button><Button size="sm" variant="ghost" onClick={() => setRejecting(false)}>{t.inbox.review.cancel}</Button></div>
        </form>
      )}
      <EditDialog item={item} config={config} open={editing} onClose={() => setEditing(false)} onDone={() => done(t.inbox.review.approved)} />
    </article>
  );
}

export default function ReviewView() {
  const { t } = useI18n();
  const config = useQuery({ queryKey: ["inbox", "config"], queryFn: fetchInboxConfig, staleTime: 60_000 });
  const review = useQuery({ queryKey: ["inbox", "review"], queryFn: fetchReview, refetchInterval: 8000 });
  return (
    <div className="space-y-5">
      <header><h1 className="text-2xl font-bold tracking-tight text-text-dark">{t.inbox.review.title}</h1><p className="mt-1 text-sm text-text-gray">{t.inbox.review.subtitle}</p></header>
      <ModeBanner outlook={config.data?.outlook_mode} clickup={config.data?.clickup_mode} />
      {review.isError && !review.data ? (
        <EmptyState icon={<AlertTriangle className="h-6 w-6" aria-hidden="true" />} title={t.inbox.errors.loadFailed} body={describeError(review.error, t)} action={<Button variant="outline" size="sm" onClick={() => review.refetch()}>{t.dashboard.retry}</Button>} />
      ) : !review.data ? <Skeleton className="h-72" /> : review.data.items.length === 0 ? <EmptyState title={t.inbox.review.empty} /> : (
        <div className="space-y-5">{review.data.items.map((item) => <ReviewCard key={item.message_id} item={item} config={config.data} />)}</div>
      )}
    </div>
  );
}
