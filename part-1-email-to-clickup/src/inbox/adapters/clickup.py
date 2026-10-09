"""ClickUp REST API v2 adapter, limited to one list and the four operations the workflow needs.

The token comes from AWS Secrets Manager (or an injected value in tests) and is never logged.
"""

from __future__ import annotations

import time
from datetime import date, datetime, time as dtime, timezone
from typing import Optional

from ..models import Member
from .base import AdapterError, HttpFn, http_json

API = "https://api.clickup.com/api/v2"


class ClickUpAdapter:
    mode = "api"

    def __init__(self, token: str, list_id: str, team_id: str, http: HttpFn = http_json, sleep=time.sleep):
        if not (token and list_id and team_id):
            raise ValueError("ClickUp token, list_id and team_id are required")
        self._token, self.list_id, self.team_id, self._http, self._sleep = token, str(list_id), str(team_id), http, sleep

    @property
    def list_url(self) -> str:
        return f"https://app.clickup.com/{self.team_id}/v/li/{self.list_id}"

    @classmethod
    def from_secret(cls, secret: dict, **kw) -> "ClickUpAdapter":
        return cls(secret["token"], secret["list_id"], secret["team_id"], **kw)

    # ------------------------------------------------------------------ transport

    def _call(self, method: str, path: str, body: Optional[dict] = None, *, safe_to_retry: bool) -> dict:
        """One call. Only reads (`safe_to_retry`) are retried, at most twice: a repeated create could duplicate a task."""
        attempts = 3 if safe_to_retry else 1
        for attempt in range(attempts):
            try:
                status, payload = self._http(method, f"{API}{path}", {"Authorization": self._token}, body, 15.0)
            except AdapterError as err:
                if err.retryable and attempt + 1 < attempts:
                    self._sleep(0.4 * (attempt + 1))
                    continue
                raise
            if status < 300:
                return payload
            retryable = status == 429 or status >= 500
            if retryable and attempt + 1 < attempts:
                self._sleep(0.4 * (attempt + 1))
                continue
            message = (payload.get("err") if isinstance(payload, dict) else None) or f"ClickUp answered {status}"
            raise AdapterError(f"clickup_{status}", str(message)[:200], retryable=retryable)
        raise AdapterError("clickup_unreachable", "ClickUp did not answer", retryable=True)

    # ------------------------------------------------------------------ reads

    def list_members(self) -> list[Member]:
        teams = self._call("GET", "/team", safe_to_retry=True).get("teams", [])
        team = next((t for t in teams if str(t.get("id")) == self.team_id), None)
        if team is None:
            raise AdapterError("clickup_workspace", "the token cannot see the configured workspace")
        return [Member(id=str(m["user"]["id"]), username=m["user"].get("username") or "", email=m["user"].get("email") or "") for m in team.get("members", [])]

    def list_statuses(self) -> list[str]:
        return [s["status"] for s in self._call("GET", f"/list/{self.list_id}", safe_to_retry=True).get("statuses", [])]

    def list_tasks(self) -> list[dict]:
        tasks: list[dict] = []
        for page in range(5):  # 500 tasks is plenty for one assessment list; larger lists need ClickUp's search or a webhook-fed index
            batch = self._call("GET", f"/list/{self.list_id}/task?include_closed=true&page={page}", safe_to_retry=True).get("tasks", [])
            tasks.extend(self._norm(t) for t in batch)
            if len(batch) < 100:
                break
        return tasks

    def get_task(self, task_id: str) -> dict:
        return self._norm(self._call("GET", f"/task/{task_id}", safe_to_retry=True))

    # ------------------------------------------------------------------ writes (never auto-retried)

    def create_task(self, fields: dict) -> dict:
        body = self._body(fields)
        if fields.get("assignee_id"):
            body["assignees"] = [int(fields["assignee_id"])]
        return self._norm(self._call("POST", f"/list/{self.list_id}/task", body, safe_to_retry=False))

    def update_task(self, task_id: str, fields: dict) -> dict:
        body = self._body(fields)
        if fields.get("assignee_id"):
            body["assignees"] = {"add": [int(fields["assignee_id"])], "rem": []}
        return self._norm(self._call("PUT", f"/task/{task_id}", body, safe_to_retry=False))

    # ------------------------------------------------------------------ mapping

    @staticmethod
    def _body(fields: dict) -> dict:
        body: dict = {}
        if fields.get("name"):
            body["name"] = fields["name"]
        if fields.get("description") is not None:
            body["description"] = fields["description"]
        if fields.get("priority"):
            body["priority"] = int(fields["priority"])
        if fields.get("status"):
            body["status"] = fields["status"]
        due = fields.get("due_date")
        if isinstance(due, date):
            body["due_date"] = int(datetime.combine(due, dtime(12, 0), tzinfo=timezone.utc).timestamp() * 1000)  # noon UTC: no day shift in any zone
            body["due_date_time"] = False
        return body

    @staticmethod
    def _norm(task: dict) -> dict:
        due = task.get("due_date")
        return {
            "id": str(task["id"]), "name": task.get("name", ""), "description": task.get("description") or task.get("text_content") or "",
            "url": task.get("url", ""), "status": (task.get("status") or {}).get("status", ""),
            "assignees": [a.get("username") or a.get("email", "") for a in task.get("assignees", [])],
            "assignee_ids": [str(a.get("id")) for a in task.get("assignees", [])],
            "priority": (task.get("priority") or {}).get("priority"),
            "due_date": datetime.fromtimestamp(int(due) / 1000, tz=timezone.utc).date().isoformat() if due else None,
        }
