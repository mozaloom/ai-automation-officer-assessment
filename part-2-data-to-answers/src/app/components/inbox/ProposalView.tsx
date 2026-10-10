"use client";

import { ExternalLink } from "lucide-react";
import type { MessageDetail } from "@/lib/api/inbox";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { ActionChip, StatusChip } from "./Chips";

const row = "grid grid-cols-[8rem_1fr] gap-3 py-1.5 text-sm";

/** One email with what the agent proposed, the real values it maps to, similar tasks, the result and the history. */
export default function ProposalView({ m }: { m: MessageDetail }) {
  const { t, dateTime, locale } = useI18n();
  const d = t.inbox.detail;
  const p = m.proposal;
  const r = p?.resolved;
  const draft = p?.triage.task;
  const notStated = <span className="text-text-light">{d.notStated}</span>;
  return (
    <div className="space-y-5" data-testid="proposal-view">
      <section aria-label={d.email}>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h3 dir="auto" className="min-w-0 flex-1 text-base font-semibold text-text-dark [overflow-wrap:anywhere]">{m.subject || "(no subject)"}</h3>
          <StatusChip status={m.status} />
        </div>
        <p className="mt-0.5 text-xs text-text-gray"><bdi dir="ltr">{m.sender_name ? `${m.sender_name} <${m.sender}>` : m.sender}</bdi> · {dateTime(m.received_at)}</p>
        <p className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-wash p-3 text-sm text-text-dark [overflow-wrap:anywhere]" dir="auto">{m.body_excerpt}</p>
        {m.web_link && <a href={m.web_link} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-brand-blue hover:underline">{d.openEmail}<ExternalLink className="h-3 w-3" aria-hidden="true" /></a>}
      </section>

      {p && (
        <section aria-label={d.proposal}>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-semibold text-text-dark">{d.proposal}</h4>
            <ActionChip action={p.action} />
            <span className="text-xs text-text-gray">{t.inbox.route[p.route]} · {d.confidence}: {Math.round(p.triage.confidence * 100)}%</span>
          </div>
          {p.reasons.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 ps-5 text-sm text-text-dark" aria-label={d.why}>{p.reasons.map((x) => <li key={x} dir="auto">{x}</li>)}</ul>
          )}
          {p.triage.rationale && <p dir="auto" className="mt-1 text-xs text-text-gray">{d.rationale}: {p.triage.rationale}</p>}

          {(p.action === "CREATE_TASK" || p.action === "UPDATE_TASK") && (
            <dl className="mt-3 divide-y divide-line border-y border-line" aria-label={d.fields}>
              <div className={row}><dt className="text-text-gray">{d.field.title}</dt><dd dir="auto" className="text-text-dark [overflow-wrap:anywhere]">{draft?.title || notStated}</dd></div>
              <div className={row}><dt className="text-text-gray">{d.field.description}</dt><dd dir="auto" className="whitespace-pre-wrap text-text-dark [overflow-wrap:anywhere]">{draft?.description || notStated}</dd></div>
              <div className={row}><dt className="text-text-gray">{d.field.assignee}</dt>
                <dd className="text-text-dark">{r?.assignee_label ? <>{r.assignee_label}</> : draft?.assignee ? <span className="text-red-700">{draft.assignee}: {d.assigneeUnknown}</span> : notStated}</dd></div>
              <div className={row}><dt className="text-text-gray">{d.field.priority}</dt>
                <dd className="text-text-dark">{r?.priority ? <>{d.priorityName[String(r.priority) as "1"]}{r.priority_source === "configured_default" && <span className="text-text-gray"> ({d.priorityDefault})</span>}</> : notStated}</dd></div>
              <div className={row}><dt className="text-text-gray">{d.field.dueDate}</dt><dd className="tabular-nums text-text-dark" dir="ltr">{r?.due_date || (draft?.due_date ? <span className="text-red-700">{draft.due_date}</span> : notStated)}</dd></div>
              <div className={row}><dt className="text-text-gray">{d.field.status}</dt><dd className="text-text-dark">{r?.status || notStated}</dd></div>
            </dl>
          )}

          {p.action === "REPLY" && p.triage.reply && (
            <div className="mt-3"><h5 className="text-xs font-medium text-text-gray">{d.reply}</h5>
              <p className="mt-1 whitespace-pre-wrap rounded-md border border-line p-3 text-sm text-text-dark [overflow-wrap:anywhere]" dir="auto">{p.triage.reply.body}</p>
              {m.draft?.draft_id && <p className="mt-1 text-xs text-text-gray">{d.draft}</p>}</div>
          )}

          {(p.action === "CREATE_TASK" || p.action === "UPDATE_TASK") && (
            <div className="mt-3"><h5 className="text-xs font-medium text-text-gray">{d.matches}</h5>
              {p.matches.length === 0 ? <p className="mt-1 text-sm text-text-gray">{d.noMatches}</p> : (
                <ul className="mt-1 divide-y divide-line rounded-md border border-line">
                  {p.matches.map((x) => (
                    <li key={x.task_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
                      <span className="min-w-0 flex-1 text-text-dark [overflow-wrap:anywhere]">{x.name}</span>
                      <span className="text-xs text-text-gray">{x.exact_marker ? d.sameEmail : d.matchScore(Math.round(x.score * 100))}</span>
                      {x.url && <a href={x.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-brand-blue hover:underline">ClickUp<ExternalLink className="h-3 w-3" aria-hidden="true" /></a>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      {m.execution && (
        <section aria-label={d.result} className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          <p className="font-medium">{m.execution.summary || d.result}</p>
          {m.execution.adopted && <p className="text-xs">{d.adopted}</p>}
          {m.execution.warning && <p className="mt-1 text-xs text-amber-800" role="note">{d.columnsSkipped}</p>}
          {m.execution.task_url && <a href={m.execution.task_url} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 text-brand-blue hover:underline">{d.openTask}<ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /></a>}
          {m.approved_by && <p className="mt-1 text-xs">{d.approvedBy(m.approved_by)}</p>}
        </section>
      )}
      {m.status === "REJECTED" && <p className="text-sm text-text-gray">{d.rejectedBy(m.rejected_by ?? "")}{m.reject_reason ? `: ${m.reject_reason}` : ""}</p>}

      {m.audit.length > 0 && (
        <section aria-label={d.history}>
          <h4 className="text-sm font-semibold text-text-dark">{d.history}</h4>
          <ol className="mt-2 space-y-1 border-s border-line ps-4">
            {[...m.audit].reverse().map((a) => (
              <li key={a.id} className="text-xs text-text-gray"><span className="font-medium text-text-dark">{t.inbox.activity.events[a.event as keyof typeof t.inbox.activity.events] ?? a.event}</span> · {a.actor} · <span className="tabular-nums" dir="ltr">{new Intl.DateTimeFormat(locale === "ar" ? "ar-JO-u-nu-latn" : "en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(a.at))}</span></li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
