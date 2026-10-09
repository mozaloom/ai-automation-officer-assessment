"""Sample adapters: a fixture mailbox and in-memory tasks. Clearly labelled SAMPLE in the UI; used for tests and as the fallback when
real credentials are missing. They support failure injection so recovery paths can be tested deterministically.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..models import Email, Member
from .base import AdapterError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "emails.json"


class _Failures:
    def __init__(self) -> None:
        self._next: dict[str, AdapterError] = {}

    def fail_next(self, operation: str, code: str = "injected", retryable: bool = True) -> None:
        self._next[operation] = AdapterError(code, f"injected failure in {operation}", retryable)

    def _maybe(self, operation: str) -> None:
        if operation in self._next:
            raise self._next.pop(operation)


class SampleMail(_Failures):
    mode = "sample"

    def __init__(self, emails: Optional[list[Email]] = None) -> None:
        super().__init__()
        raw = json.loads(FIXTURES.read_text(encoding="utf-8")) if emails is None else None
        self.emails: list[Email] = emails if emails is not None else [Email.model_validate(e) for e in raw]
        self.drafts: list[dict] = []
        self.sent: list[dict] = []

    def add(self, email: Email) -> None:
        self.emails.append(email)

    def list_recent_emails(self, limit: int = 25) -> list[Email]:
        self._maybe("list_recent_emails")
        return sorted(self.emails, key=lambda e: e.received_at, reverse=True)[:limit]

    def get_email(self, message_id: str) -> Email:
        self._maybe("get_email")
        found = next((e for e in self.emails if e.message_id == message_id), None)
        if not found:
            raise AdapterError("not_found", "email not found")
        return found

    def draft_reply(self, message_id: str, body: str) -> dict:
        self._maybe("draft_reply")
        self.drafts.append({"message_id": message_id, "body": body})
        return {"draft_id": f"draft-{len(self.drafts)}"}

    def send_reply(self, message_id: str, body: str) -> dict:
        self._maybe("send_reply")
        self.sent.append({"message_id": message_id, "body": body})
        return {"sent": True}


class SampleTasks(_Failures):
    mode = "sample"

    def __init__(self, tasks: Optional[list[dict]] = None) -> None:
        super().__init__()
        self.members = [Member(id="101", username="Mohammed Zaloom", email="mohammed@medgan.ai"), Member(id="102", username="Ahmad Haddad", email="ahmad@medgan.ai"), Member(id="103", username="Sara Nasser", email="sara@medgan.ai")]
        self.statuses = ["to do", "in progress", "blocked", "done"]
        self.tasks: dict[str, dict] = {t["id"]: t for t in (tasks if tasks is not None else self._seed())}
        self._seq = 1000
        self.created: list[dict] = []
        self.updated: list[dict] = []

    @staticmethod
    def _seed() -> list[dict]:
        base = {"description": "", "assignees": [], "assignee_ids": [], "priority": None, "due_date": None}
        return [
            {**base, "id": "t1", "name": "Prepare the Q3 marketing report", "status": "in progress", "url": "https://app.clickup.com/t/t1", "assignees": ["Sara Nasser"], "assignee_ids": ["103"], "due_date": "2026-10-20"},
            {**base, "id": "t2", "name": "Website homepage banner redesign", "status": "to do", "url": "https://app.clickup.com/t/t2"},
        ]

    def list_members(self) -> list[Member]:
        self._maybe("list_members")
        return list(self.members)

    def list_statuses(self) -> list[str]:
        return list(self.statuses)

    def list_tasks(self) -> list[dict]:
        self._maybe("list_tasks")
        return deepcopy(list(self.tasks.values()))

    def get_task(self, task_id: str) -> dict:
        self._maybe("get_task")
        if task_id not in self.tasks:
            raise AdapterError("clickup_404", "task not found")
        return deepcopy(self.tasks[task_id])

    def create_task(self, fields: dict) -> dict:
        self._maybe("create_task")
        self._seq += 1
        member = next((m for m in self.members if m.id == str(fields.get("assignee_id"))), None)
        due = fields.get("due_date")
        task = {"id": f"t{self._seq}", "name": fields["name"], "description": fields.get("description") or "", "url": f"https://app.clickup.com/t/t{self._seq}",
                "status": fields.get("status") or self.statuses[0], "assignees": [member.username] if member else [], "assignee_ids": [member.id] if member else [],
                "priority": {1: "urgent", 2: "high", 3: "normal", 4: "low"}.get(fields.get("priority")), "due_date": due.isoformat() if isinstance(due, date) else None}
        self.tasks[task["id"]] = task
        self.created.append(deepcopy(task))
        return deepcopy(task)

    def update_task(self, task_id: str, fields: dict) -> dict:
        self._maybe("update_task")
        task = self.tasks[task_id]
        for key in ("name", "description", "status"):
            if fields.get(key):
                task[key] = fields[key]
        if fields.get("priority"):
            task["priority"] = {1: "urgent", 2: "high", 3: "normal", 4: "low"}[fields["priority"]]
        if isinstance(fields.get("due_date"), date):
            task["due_date"] = fields["due_date"].isoformat()
        self.updated.append({"id": task_id, **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()}})
        return deepcopy(task)
