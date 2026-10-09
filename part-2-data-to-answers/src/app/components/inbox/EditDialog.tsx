"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X } from "lucide-react";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { describeError } from "@/lib/api/errors";
import { editItem, type EditChanges, type InboxConfig, type MessageDetail } from "@/lib/api/inbox";
import { ApiError } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

const PRIORITIES = ["urgent", "high", "normal", "low"] as const;
const field = "h-10 w-full rounded-md border border-[#d0d5dd] bg-white px-3 text-sm text-text-dark focus-visible:border-brand-blue focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-blue/15";

/** Edit the proposal, then approve it in one step. The server re-validates every value against real ClickUp members and statuses. */
export default function EditDialog({ item, config, open, onClose, onDone }: { item: MessageDetail; config?: InboxConfig; open: boolean; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const triage = item.proposal?.triage;
  const undecided = item.proposal?.action === "HUMAN_REVIEW"; // the agent could not decide: the reviewer chooses what happens
  const [choice, setChoice] = useState<"" | "CREATE_TASK" | "REPLY" | "IGNORE">("");
  const isReply = undecided ? choice === "REPLY" : item.proposal?.action === "REPLY";
  const isDismiss = undecided && choice === "IGNORE";
  const [task, setTask] = useState({ title: triage?.task?.title ?? "", description: triage?.task?.description ?? "", assignee: item.proposal?.resolved?.assignee_label ?? "", priority: triage?.task?.priority ?? "", due_date: triage?.task?.due_date ?? "", status: triage?.task?.status ?? "" });
  const [reply, setReply] = useState(triage?.reply?.body ?? "");
  const mutation = useMutation({ mutationFn: (changes: EditChanges) => editItem(item.message_id, changes), onSuccess: onDone });

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const problems = mutation.error instanceof ApiError && Array.isArray((mutation.error.payload as { error?: { problems?: string[] } } | undefined)?.error?.problems) ? (mutation.error.payload as { error: { problems: string[] } }).error.problems : [];
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (undecided && !choice) return;
    const action = undecided ? { action: choice as "CREATE_TASK" | "REPLY" | "IGNORE" } : {};
    mutation.mutate(isDismiss ? action : isReply ? { ...action, reply_body: reply } : { ...action, task: { title: task.title || null, description: task.description || null, assignee: task.assignee || null, priority: task.priority || null, due_date: task.due_date || null, status: task.status || null } });
  };
  const f = t.inbox.detail.field;
  return (
    <dialog ref={ref} aria-label={undecided ? t.inbox.review.decideTitle : t.inbox.review.editTitle} onClose={onClose} className="m-auto w-[min(36rem,calc(100vw-2rem))] rounded-xl border border-line p-0 text-text-dark backdrop:bg-black/40">
      <form onSubmit={submit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3"><h2 className="text-lg font-semibold">{undecided ? t.inbox.review.decideTitle : t.inbox.review.editTitle}</h2>
          <button type="button" onClick={onClose} aria-label={t.common.close} className="rounded-md p-1.5 hover:bg-wash"><X className="h-4 w-4" aria-hidden="true" /></button></div>
        {undecided && (
          <label className="flex flex-col gap-1.5 text-sm font-medium">{t.inbox.review.whatToDo}
            <select value={choice} onChange={(e) => setChoice(e.target.value as typeof choice)} className={field} required>
              <option value="">{t.inbox.review.chooseAction}</option>
              {(["CREATE_TASK", "REPLY", "IGNORE"] as const).map((c) => <option key={c} value={c}>{t.inbox.review.choice[c]}</option>)}
            </select></label>
        )}
        {isDismiss ? <p className="rounded-md bg-wash px-3 py-2 text-sm text-text-gray">{t.inbox.review.dismissNote}</p> : undecided && !choice ? null : isReply ? (
          <label className="flex flex-col gap-1.5 text-sm font-medium">{t.inbox.review.replyText}<textarea value={reply} onChange={(e) => setReply(e.target.value)} rows={7} maxLength={6000} className={`${field} h-auto py-2 font-normal`} dir="auto" /></label>
        ) : (
          <>
            <Input label={f.title} value={task.title} onChange={(e) => setTask({ ...task, title: e.target.value })} maxLength={300} />
            <label className="flex flex-col gap-1.5 text-sm font-medium">{f.description}<textarea value={task.description} onChange={(e) => setTask({ ...task, description: e.target.value })} rows={4} className={`${field} h-auto py-2 font-normal`} dir="auto" /></label>
            <label className="flex flex-col gap-1.5 text-sm font-medium">{f.assignee}
              <select value={task.assignee} onChange={(e) => setTask({ ...task, assignee: e.target.value })} className={field}>
                <option value="">{t.inbox.review.pickAssignee}</option>
                {(config?.members ?? []).map((m) => <option key={m.id} value={m.email || m.name}>{m.name}</option>)}
              </select><span className="text-xs font-normal text-text-gray">{t.inbox.review.assigneeHelp}</span></label>
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="flex flex-col gap-1.5 text-sm font-medium">{f.priority}<select value={task.priority} onChange={(e) => setTask({ ...task, priority: e.target.value })} className={field}><option value="">{t.inbox.review.noChange}</option>{PRIORITIES.map((p) => <option key={p} value={p}>{t.inbox.detail.priorityName[String(PRIORITIES.indexOf(p) + 1) as "1"]}</option>)}</select></label>
              <label className="flex flex-col gap-1.5 text-sm font-medium">{f.dueDate}<input type="date" value={task.due_date} onChange={(e) => setTask({ ...task, due_date: e.target.value })} className={field} dir="ltr" /></label>
              <label className="flex flex-col gap-1.5 text-sm font-medium">{f.status}<select value={task.status} onChange={(e) => setTask({ ...task, status: e.target.value })} className={field}><option value="">{t.inbox.review.noChange}</option>{(config?.statuses ?? []).map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
            </div>
          </>
        )}
        {mutation.isError && (
          <div role="alert" className="rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-800">
            <p>{describeError(mutation.error, t)}</p>{problems.length > 0 && <ul className="mt-1 list-disc ps-5 text-xs">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
          </div>
        )}
        <div className="flex justify-end gap-2"><Button variant="outline" size="sm" onClick={onClose}>{t.inbox.review.cancel}</Button><Button type="submit" size="sm" loading={mutation.isPending} disabled={undecided && !choice}>{undecided ? t.inbox.review.saveDecision : t.inbox.review.save}</Button></div>
      </form>
    </dialog>
  );
}
