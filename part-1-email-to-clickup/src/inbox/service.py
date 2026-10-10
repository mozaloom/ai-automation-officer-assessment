"""The workflow: sync -> idempotent claim -> triage -> deterministic resolution -> policy -> execute or review.

Responsibilities are kept apart on purpose:
- the agent (a `Triager`) only proposes;
- this service validates, resolves, applies policy, enforces approval state and talks to ClickUp/Outlook;
- ClickUp stays the system of record for tasks.
No decision about duplicates, authorization or approval is ever left to a model.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, Protocol

from pydantic import ValidationError

from .adapters.base import AdapterError, MailAdapter, TaskAdapter
from .config import MARKER, Settings
from .models import Action, Email, Match, Principal, Proposal, ResolvedTask, Status, Triage
from .policy import decide
from .redact import mask_address, redact
from .resolve import find_matches, resolve_task
from .store import Store, iso, utcnow

log = logging.getLogger("inbox")


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    """The request is valid but the message is not in a state that allows it (e.g. already approved)."""


class Invalid(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class Triager(Protocol):
    def triage(self, email: Email, context: dict) -> Triage: ...


class TriageUnavailable(Exception):
    """The agent could not be reached (timeout, throttling): retryable, unlike an invalid answer."""


class InboxService:
    def __init__(self, settings: Settings, store: Store, mail: MailAdapter, tasks: TaskAdapter, triager: Triager, clock: Callable[[], datetime] = utcnow):
        self.settings, self.store, self.mail, self.tasks, self.triager, self.clock = settings, store, mail, tasks, triager, clock

    # ------------------------------------------------------------------ authorization

    def _require_reviewer(self, principal: Optional[Principal]) -> Principal:
        if principal is None or not principal.user_id:
            raise Forbidden("authentication required")
        if self.settings.reviewer_group not in principal.groups:
            self._audit("-", "unauthorized", principal, outcome="denied", detail=f"not in {self.settings.reviewer_group}")
            raise Forbidden("you are not allowed to do this")
        return principal

    @staticmethod
    def _who(principal: Optional[Principal]) -> str:
        return (principal.email or principal.user_id) if principal else "system"

    def _audit(self, message_id: str, event: str, principal: Optional[Principal] = None, **fields: Any) -> None:
        self.store.append_audit(message_id, {"event": event, "actor": self._who(principal), **{k: v for k, v in fields.items() if v is not None}})
        log.info(event, extra={"event": event, "message_id": message_id, "actor": mask_address(self._who(principal)), **{k: v for k, v in fields.items() if k in ("action", "outcome", "task_id")}})

    # ------------------------------------------------------------------ sync and processing

    def sync(self, principal: Optional[Principal] = None, system: bool = False) -> dict:
        """Fetch recent mail and process each message once. Safe to run repeatedly: already-seen messages are recognised, not redone.
        `system=True` is for the scheduler and the verified Graph webhook; a person must be a reviewer."""
        if not system:
            self._require_reviewer(principal)
        try:
            emails = self.mail.list_recent_emails(self.settings.sync_limit)
        except AdapterError as err:
            self._audit("-", "sync_failed", principal, outcome="failed", detail=err.code)
            raise
        result = {"fetched": len(emails), "new": 0, "duplicates": 0, "failed": 0, "mode": self.mail.mode}
        for email in emails:
            outcome = self.process(email)["outcome"]
            result["new" if outcome == "processed" else "duplicates" if outcome == "duplicate" else "failed"] += 1
        self._audit("-", "sync", principal, outcome="ok", detail=f"{result['new']} new, {result['duplicates']} already known, {result['failed']} failed")
        return result

    def process(self, email: Email) -> dict:
        now = self.clock()
        item = {
            "status": Status.PROCESSING.value, "lease_until": iso(now + timedelta(seconds=self.settings.lease_seconds)), "attempts": 1,
            "received_at": iso(email.received_at), "sender": email.sender, "sender_name": email.sender_name, "subject": email.subject[:200],
            "body_excerpt": email.body[: self.settings.body_excerpt_chars], "conversation_id": email.conversation_id, "created_at": iso(now), "web_link": email.web_link,
        }
        if not self.store.claim(email.message_id, item):
            # Same message again (webhook retry, second sync, concurrent worker). Only an abandoned lease may be taken over.
            if self.store.acquire(email.message_id, [], iso(now + timedelta(seconds=self.settings.lease_seconds)), iso(now)):
                self._audit(email.message_id, "takeover", outcome="resumed", detail="previous worker's lease expired")
                return self._pipeline(email)
            current = self.store.get(email.message_id) or {}
            self._audit(email.message_id, "duplicate_delivery", outcome="ignored", detail=current.get("status"))
            return {"outcome": "duplicate", "status": current.get("status")}
        self._audit(email.message_id, "received", detail=redact(email.subject))
        return self._pipeline(email)

    def _pipeline(self, email: Email) -> dict:
        mid = email.message_id
        try:
            members, statuses, tasks = self.tasks.list_members(), self.tasks.list_statuses(), self.tasks.list_tasks()
            context = {"members": [m.username or m.email for m in members], "statuses": statuses,
                       "tasks": [{"id": t["id"], "name": t["name"], "status": t["status"], "assignees": t.get("assignees", [])} for t in tasks][:60]}
            triage = self._triage(email, context)
        except (AdapterError, TriageUnavailable) as err:
            return self._fail(mid, getattr(err, "code", "triage_unavailable"), str(err), retryable=True, stage="triage")

        resolved: Optional[ResolvedTask] = None
        matches: list[Match] = []
        if triage.task is not None:
            resolved = resolve_task(triage.task, members, statuses, email.received_at.date(), self.settings.policy, creating=triage.action == Action.CREATE_TASK)
        if triage.action in (Action.CREATE_TASK, Action.UPDATE_TASK):
            query = (triage.task.title if triage.task and triage.task.title else None) or next((t["name"] for t in tasks if t["id"] == triage.target_task_id), email.subject)
            matches = find_matches(query, mid, tasks)

        # A task already carrying this email's marker means an earlier attempt created it and then lost the answer: adopt, do not create again.
        adopted = next((m for m in matches if m.exact_marker), None)
        if triage.action == Action.CREATE_TASK and adopted:
            proposal = Proposal(action=Action.CREATE_TASK, triage=triage, resolved=resolved, matches=matches, route="auto", reasons=["task already exists for this email"])
            self.store.update(mid, {"proposal": proposal.model_dump(mode="json")})
            self.store.transition(mid, [Status.PROCESSING], Status.EXECUTED, {"execution": {"task_id": adopted.task_id, "task_url": adopted.url, "adopted": True, "at": iso(self.clock())}})
            self._audit(mid, "adopted_existing_task", action=Action.CREATE_TASK.value, outcome="ok", task_id=adopted.task_id)
            return {"outcome": "processed", "status": Status.EXECUTED.value, "task_id": adopted.task_id}

        decision = decide(triage, email, resolved, matches, self.settings.policy)
        proposal = Proposal(action=decision.action, triage=triage, resolved=resolved, matches=matches, route=decision.route, reasons=decision.reasons)
        draft: dict = {}
        if decision.action == Action.REPLY and triage.reply:
            try:
                draft = self.mail.draft_reply(mid, triage.reply.body)  # a draft in the mailbox: visible to the reviewer, sends nothing
            except AdapterError:
                draft = {}
        self.store.update(mid, {"proposal": proposal.model_dump(mode="json"), "draft": draft or None})
        self._audit(mid, "triaged", action=decision.action.value, outcome=decision.route, detail="; ".join(decision.reasons)[:300] or None)

        if decision.route == "review":
            self.store.transition(mid, [Status.PROCESSING], Status.PENDING_REVIEW)
            self._audit(mid, "queued_for_review", action=decision.action.value, outcome="pending")
            return {"outcome": "processed", "status": Status.PENDING_REVIEW.value}
        if decision.action == Action.IGNORE:
            self.store.transition(mid, [Status.PROCESSING], Status.IGNORED)
            self._audit(mid, "ignored", action=Action.IGNORE.value, outcome="ok")
            return {"outcome": "processed", "status": Status.IGNORED.value}
        if not self.store.transition(mid, [Status.PROCESSING], Status.EXECUTING, {"approved_by": "policy:auto"}):
            return {"outcome": "duplicate", "status": (self.store.get(mid) or {}).get("status")}
        return {"outcome": "processed", **self._execute(mid, proposal, actor="policy:auto")}

    def _triage(self, email: Email, context: dict) -> Triage:
        try:
            return self.triager.triage(email, context)
        except TriageUnavailable:
            raise
        except (ValidationError, ValueError, KeyError) as err:
            # An invalid answer from the agent is never executed: it becomes a review item for a person.
            self._audit(email.message_id, "triage_invalid", outcome="fallback", detail=type(err).__name__)
            return Triage(action=Action.HUMAN_REVIEW, confidence=0.0, rationale="The agent's answer could not be validated, so a person must decide.")

    # ------------------------------------------------------------------ execution

    def _execute(self, message_id: str, proposal: Proposal, actor: str) -> dict:
        """Perform the external action. Only called after the state moved to EXECUTING by a conditional write."""
        item = self.store.get(message_id) or {}
        try:
            result = self._run_action(message_id, proposal, item)
        except AdapterError as err:
            return self._fail(message_id, err.code, str(err), err.retryable, stage="execute", from_status=Status.EXECUTING)
        self.store.transition(message_id, [Status.EXECUTING], Status.EXECUTED, {"execution": {**result, "at": iso(self.clock())}, "error": None})
        self._audit(message_id, "executed", action=proposal.action.value, outcome="ok", task_id=result.get("task_id"), detail=result.get("summary"))
        return {"status": Status.EXECUTED.value, **result}

    def _run_action(self, message_id: str, proposal: Proposal, item: dict) -> dict:
        action, r = proposal.action, proposal.resolved
        if action == Action.CREATE_TASK and r:
            existing = next((m for m in find_matches(r.title or "", message_id, self.tasks.list_tasks()) if m.exact_marker), None)
            if existing:  # retry after a lost answer: the earlier create did succeed
                return {"task_id": existing.task_id, "task_url": existing.url, "adopted": True, "summary": "task already existed for this email"}
            footer = f"\n\n---\nSource email from {item.get('sender', '')}: {item.get('subject', '')[:120]}\n{MARKER.format(message_id)}"
            custom = {"Sender Email Address": item.get("sender"), "Message Received Date": item.get("received_at"), "Source Message Link": item.get("web_link"),
                      "Inbox Action": "Escalate" if proposal.triage.sensitive else "Route"}  # facts about the email and where the task was routed; nothing is guessed
            task = self.tasks.create_task({"name": r.title, "description": (r.description or "") + footer, "assignee_id": r.assignee_id, "priority": r.priority, "due_date": r.due_date, "status": r.status, "custom": custom})
            result = {"task_id": task["id"], "task_url": task["url"], "summary": f"created '{task['name'][:80]}'", "fields": self._fields_summary(r)}
            if task.get("custom_skipped"):
                result["warning"] = "the task was created without the list's custom columns (ClickUp refused them: " + task["custom_skipped"] + ")"
                self._audit(message_id, "custom_fields_skipped", outcome="warning", task_id=task["id"], detail=task["custom_skipped"])
            return result
        if action == Action.UPDATE_TASK and r:
            fields = {k: v for k, v in {"description": r.description, "status": r.status, "due_date": r.due_date, "assignee_id": r.assignee_id}.items() if v}
            if proposal.triage.task and proposal.triage.task.priority:
                fields["priority"] = r.priority
            current = self.tasks.get_task(proposal.triage.target_task_id or "")
            if r.description:
                fields["description"] = (current.get("description") or "").rstrip() + f"\n\nUpdate from email ({item.get('sender', '')}): {r.description}\n{MARKER.format(message_id)}"
            task = self.tasks.update_task(current["id"], fields)
            return {"task_id": task["id"], "task_url": task["url"], "summary": f"updated '{task['name'][:80]}'", "changes": sorted(fields)}
        if action == Action.REPLY and proposal.triage.reply:
            self.mail.send_reply(message_id, proposal.triage.reply.body, draft_id=(item.get("draft") or {}).get("draft_id"))  # sends the draft the reviewer saw, with their final text
            return {"sent": True, "summary": "reply sent"}
        raise AdapterError("nothing_to_execute", "the proposal has nothing executable")

    @staticmethod
    def _fields_summary(r: ResolvedTask) -> dict:
        return {"assignee": r.assignee_label, "priority": r.priority, "priority_source": r.priority_source, "due_date": r.due_date.isoformat() if r.due_date else None, "status": r.status}

    def _fail(self, message_id: str, code: str, message: str, retryable: bool, stage: str, from_status: Status = Status.PROCESSING) -> dict:
        error = {"code": code, "message": message[:300], "retryable": retryable, "stage": stage, "at": iso(self.clock())}
        self.store.transition(message_id, [from_status], Status.FAILED, {"error": error})
        self._audit(message_id, "failed", outcome="failed", detail=f"{stage}: {code}")
        return {"outcome": "failed", "status": Status.FAILED.value, "error": error}

    # ------------------------------------------------------------------ human review (all enforced here, never by the client)

    def _pending(self, message_id: str) -> tuple[dict, Proposal]:
        item = self.store.get(message_id)
        if not item:
            raise NotFound(message_id)
        if item["status"] != Status.PENDING_REVIEW.value or not item.get("proposal"):
            raise Conflict(f"this email is {item['status'].lower().replace('_', ' ')}, not waiting for review")
        return item, Proposal.model_validate(item["proposal"])

    def executable_problems(self, proposal: Proposal) -> list[str]:
        """Why a proposal cannot run yet. A reviewer must fix these by editing; they are never papered over."""
        r, problems = proposal.resolved, []
        if proposal.action in (Action.CREATE_TASK, Action.UPDATE_TASK):
            if r is None:
                return ["no task fields"]
            problems.extend(r.problems)
            if proposal.action == Action.CREATE_TASK:
                problems.extend(f"missing {name}" for name, ok in (("title", r.title), ("assignee", r.assignee_id)) if not ok)
            elif not proposal.triage.target_task_id:
                problems.append("missing the task to update")
        elif proposal.action == Action.REPLY:
            if not proposal.triage.reply or not proposal.triage.reply.body.strip():
                problems.append("missing reply text")
        else:
            problems.append(f"{proposal.action.value} has nothing to execute")
        return problems

    def approve(self, message_id: str, principal: Optional[Principal]) -> dict:
        principal = self._require_reviewer(principal)
        _, proposal = self._pending(message_id)
        problems = self.executable_problems(proposal)
        if problems:
            raise Invalid(problems)
        # The conditional write is the approval gate: only one caller can move PENDING_REVIEW -> EXECUTING.
        if not self.store.transition(message_id, [Status.PENDING_REVIEW], Status.EXECUTING, {"approved_by": self._who(principal), "approved_at": iso(self.clock())}):
            raise Conflict("this email was already handled")
        self._audit(message_id, "approved", principal, action=proposal.action.value, outcome="approved")
        return self._execute(message_id, proposal, actor=self._who(principal))

    def edit(self, message_id: str, principal: Optional[Principal], changes: dict) -> dict:
        """Approve with edits. The edited fields are re-validated and re-resolved from scratch; the client sends values, not approval."""
        principal = self._require_reviewer(principal)
        item, proposal = self._pending(message_id)
        triage = proposal.triage.model_dump()
        action = proposal.action
        if action == Action.HUMAN_REVIEW:  # the agent could not decide: the reviewer does, by choosing what should happen
            chosen = changes.get("action")
            if chosen not in (Action.CREATE_TASK.value, Action.UPDATE_TASK.value, Action.REPLY.value, Action.IGNORE.value):
                raise Invalid(["choose what to do: create a task, update a task, reply, or dismiss"])
            action = Action(chosen)
            triage["action"] = action.value
            triage["sensitive"] = False if action == Action.IGNORE else triage.get("sensitive", False)
            if action == Action.IGNORE:
                if not self.store.transition(message_id, [Status.PENDING_REVIEW], Status.IGNORED, {"approved_by": self._who(principal), "approved_at": iso(self.clock())}):
                    raise Conflict("this email was already handled")
                self._audit(message_id, "ignored", principal, action=Action.IGNORE.value, outcome="dismissed", detail="dismissed by a reviewer")
                return {"status": Status.IGNORED.value}
        try:
            if action in (Action.CREATE_TASK, Action.UPDATE_TASK):
                task = {**(triage.get("task") or {}), **{k: v for k, v in (changes.get("task") or {}).items() if k in ("title", "description", "assignee", "priority", "due_date", "status")}}
                triage["task"] = task
                if changes.get("target_task_id"):
                    triage["target_task_id"] = str(changes["target_task_id"])
            if action == Action.REPLY and changes.get("reply_body") is not None:
                triage["reply"] = {**(triage.get("reply") or {}), "body": changes["reply_body"]}
            edited = Triage.model_validate(triage)
            if edited.action == Action.HUMAN_REVIEW and action != Action.HUMAN_REVIEW:  # the chosen action lacked what it needs
                raise Invalid([f"missing {', '.join(edited.missing_fields)}"])
        except ValidationError as err:
            raise Invalid([f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors()[:5]]) from None
        members, statuses, tasks = self.tasks.list_members(), self.tasks.list_statuses(), self.tasks.list_tasks()
        received = datetime.fromisoformat(item["received_at"].replace("Z", "+00:00")).date()
        resolved = resolve_task(edited.task, members, statuses, received, self.settings.policy, creating=edited.action == Action.CREATE_TASK) if edited.task else None
        query = (edited.task.title if edited.task and edited.task.title else item.get("subject", ""))
        new = Proposal(action=edited.action, triage=edited, resolved=resolved, matches=find_matches(query, message_id, tasks), route="review", reasons=proposal.reasons, version=proposal.version + 1, edited_by=self._who(principal))
        problems = self.executable_problems(new)
        if problems:
            raise Invalid(problems)
        if not self.store.transition(message_id, [Status.PENDING_REVIEW], Status.EXECUTING, {"proposal": new.model_dump(mode="json"), "original_proposal": item["proposal"], "approved_by": self._who(principal), "approved_at": iso(self.clock())}):
            raise Conflict("this email was already handled")
        self._audit(message_id, "edited_and_approved", principal, action=new.action.value, outcome="approved", detail="edited: " + ", ".join(sorted(changes)))
        return self._execute(message_id, new, actor=self._who(principal))

    def reject(self, message_id: str, principal: Optional[Principal], reason: str = "") -> dict:
        principal = self._require_reviewer(principal)
        self._pending(message_id)
        if not self.store.transition(message_id, [Status.PENDING_REVIEW], Status.REJECTED, {"rejected_by": self._who(principal), "reject_reason": reason[:500], "rejected_at": iso(self.clock())}):
            raise Conflict("this email was already handled")
        self._audit(message_id, "rejected", principal, outcome="rejected", detail=reason[:200] or None)
        draft_id = ((self.store.get(message_id) or {}).get("draft") or {}).get("draft_id")
        if draft_id:  # the reply draft will never be sent: do not leave it in the mailbox. Nothing is sent or created.
            try:
                self.mail.discard_draft(draft_id)
                self._audit(message_id, "draft_discarded", principal, outcome="ok")
            except AdapterError as err:
                self._audit(message_id, "draft_discard_failed", principal, outcome="failed", detail=err.code)
        return {"status": Status.REJECTED.value}

    def retry(self, message_id: str, principal: Optional[Principal]) -> dict:
        """Re-run a failed message. Execution failures retry from the stored proposal (a create first looks for its own marker)."""
        principal = self._require_reviewer(principal)
        item = self.store.get(message_id)
        if not item:
            raise NotFound(message_id)
        if item["status"] != Status.FAILED.value:
            raise Conflict("only failed emails can be retried")
        error = item.get("error") or {}
        if not error.get("retryable", False):
            raise Conflict("this failure is not retryable; reject or edit the item instead")
        self._audit(message_id, "retried", principal, outcome="started", detail=error.get("stage"))
        if error.get("stage") == "execute" and item.get("proposal") and item.get("approved_by"):
            if not self.store.transition(message_id, [Status.FAILED], Status.EXECUTING, {"error": None}):
                raise Conflict("already being retried")
            return self._execute(message_id, Proposal.model_validate(item["proposal"]), actor=self._who(principal))
        if not self.store.acquire(message_id, [Status.FAILED], iso(self.clock() + timedelta(seconds=self.settings.lease_seconds)), iso(self.clock())):
            raise Conflict("already being retried")
        return self._pipeline(self.mail.get_email(message_id))

    # ------------------------------------------------------------------ read models for the UI

    def list_messages(self, limit: int = 100) -> list[dict]:
        return [self._summary(i) for i in self.store.list_messages(limit)]

    def list_review(self) -> list[dict]:
        return [self.message_view(i["message_id"]) for i in self.store.list_by_status(Status.PENDING_REVIEW)]

    def message_view(self, message_id: str) -> dict:
        item = self.store.get(message_id)
        if not item:
            raise NotFound(message_id)
        problems: list[str] = []
        if item["status"] == Status.PENDING_REVIEW.value and item.get("proposal"):
            problems = self.executable_problems(Proposal.model_validate(item["proposal"]))  # why Approve is not possible yet (the UI shows it; the server enforces it)
        return {**self._summary(item), "body_excerpt": item.get("body_excerpt", ""), "can_approve": item["status"] == Status.PENDING_REVIEW.value and not problems, "problems": problems, "proposal": item.get("proposal"), "execution": item.get("execution"), "error": item.get("error"),
                "draft": item.get("draft"), "web_link": item.get("web_link"), "approved_by": item.get("approved_by"), "rejected_by": item.get("rejected_by"), "reject_reason": item.get("reject_reason"),
                "audit": self.store.list_audit(message_id, 50)}

    def list_activity(self, limit: int = 100) -> list[dict]:
        return self.store.list_audit(None, limit)

    @staticmethod
    def _summary(item: dict) -> dict:
        proposal = item.get("proposal") or {}
        return {"message_id": item["message_id"], "status": item["status"], "sender": item.get("sender"), "sender_name": item.get("sender_name"), "subject": item.get("subject"),
                "received_at": item.get("received_at"), "action": proposal.get("action"), "route": proposal.get("route"), "task_id": (item.get("execution") or {}).get("task_id"),
                "task_url": (item.get("execution") or {}).get("task_url"), "error_code": (item.get("error") or {}).get("code")}
