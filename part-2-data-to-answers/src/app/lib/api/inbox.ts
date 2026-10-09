import { apiFetch } from "./client";

export type MessageStatus = "PROCESSING" | "PENDING_REVIEW" | "EXECUTING" | "EXECUTED" | "IGNORED" | "REJECTED" | "FAILED";
export type ActionType = "CREATE_TASK" | "UPDATE_TASK" | "REPLY" | "IGNORE" | "HUMAN_REVIEW";

export interface MessageSummary {
  message_id: string; status: MessageStatus; sender: string; sender_name: string; subject: string; received_at: string;
  action: ActionType | null; route: "auto" | "review" | null; task_id: string | null; task_url: string | null; error_code: string | null;
}
export interface SyncState { state: "running" | "done" | "failed"; started_at?: string; finished_at?: string; fetched?: number; new?: number; duplicates?: number; failed?: number; error?: string; already_running?: boolean }
export interface MessageList { messages: MessageSummary[]; sync: SyncState | null; mode: { outlook: string; clickup: string } }

export interface TaskDraft { title: string | null; description: string | null; assignee: string | null; priority: string | null; due_date: string | null; status: string | null }
export interface ResolvedTask { title: string | null; description: string | null; assignee_id: string | null; assignee_label: string | null; priority: number | null; priority_source: "email" | "configured_default" | "none"; due_date: string | null; status: string | null; problems: string[] }
export interface Match { task_id: string; name: string; url: string; status: string; score: number; exact_marker: boolean }
export interface Proposal {
  action: ActionType; route: "auto" | "review"; reasons: string[]; version: number; edited_by: string | null; matches: Match[]; resolved: ResolvedTask | null;
  triage: { action: ActionType; confidence: number; rationale: string; task: TaskDraft | null; target_task_id: string | null; reply: { body: string; subject: string | null; to: string[] } | null; missing_fields: string[]; sensitive: boolean; sensitivity_reasons: string[] };
}
export interface AuditEvent { message_id: string; at: string; id: string; event: string; actor: string; action?: string; outcome?: string; task_id?: string; detail?: string }
export interface MessageDetail extends MessageSummary {
  body_excerpt: string; can_approve: boolean; problems: string[]; proposal: Proposal | null;
  execution: { task_id?: string; task_url?: string; summary?: string; sent?: boolean; adopted?: boolean; at?: string; fields?: Record<string, unknown>; changes?: string[] } | null;
  error: { code: string; message: string; retryable: boolean; stage: string; at: string } | null;
  draft: { draft_id?: string } | null; approved_by?: string; rejected_by?: string; reject_reason?: string; audit: AuditEvent[];
}
export interface InboxConfig {
  mailbox: string; outlook_mode: string; clickup_mode: string; reviewer_group: string; clickup_list_url: string | null;
  members: { id: string; name: string; email: string }[]; statuses: string[];
  policy: { auto_send_replies: boolean; min_confidence: number; duplicate_high: number; duplicate_low: number; default_priority: string | null; default_status: string | null; required_for_create: string[] };
}
export interface EditChanges { action?: "CREATE_TASK" | "UPDATE_TASK" | "REPLY" | "IGNORE"; task?: Partial<Record<"title" | "description" | "assignee" | "priority" | "due_date" | "status", string | null>>; reply_body?: string; target_task_id?: string }

export const fetchInboxConfig = () => apiFetch<InboxConfig>("/inbox/config");
export const fetchMessages = () => apiFetch<MessageList>("/inbox/messages");
export const fetchMessage = (id: string) => apiFetch<MessageDetail>(`/inbox/messages/${encodeURIComponent(id)}`);
export const fetchReview = () => apiFetch<{ items: MessageDetail[] }>("/inbox/review");
export const fetchActivity = () => apiFetch<{ events: AuditEvent[] }>("/inbox/activity");
export const startSync = () => apiFetch<SyncState>("/inbox/sync", { method: "POST", body: {} });
export const approveItem = (id: string) => apiFetch<Record<string, unknown>>(`/inbox/review/${encodeURIComponent(id)}/approve`, { method: "POST", body: {} });
export const rejectItem = (id: string, reason: string) => apiFetch<Record<string, unknown>>(`/inbox/review/${encodeURIComponent(id)}/reject`, { method: "POST", body: { reason } });
export const editItem = (id: string, changes: EditChanges) => apiFetch<Record<string, unknown>>(`/inbox/review/${encodeURIComponent(id)}/edit`, { method: "POST", body: changes });
export const retryItem = (id: string) => apiFetch<Record<string, unknown>>(`/inbox/messages/${encodeURIComponent(id)}/retry`, { method: "POST", body: {} });
