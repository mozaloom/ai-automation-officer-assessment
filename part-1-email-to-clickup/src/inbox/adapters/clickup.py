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
        self._fields: Optional[dict[str, dict]] = None

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

    def custom_fields(self) -> dict[str, dict]:
        """The list's custom fields by lower-case name (read once per adapter). The assessment list has Sender Email Address, Message Received Date,
        Source Message Link, Inbox Action and Reply Required; a list without a field simply does not get that value."""
        if self._fields is None:
            found = self._call("GET", f"/list/{self.list_id}/field", safe_to_retry=True).get("fields", [])
            self._fields = {f["name"].strip().lower(): f for f in found}
        return self._fields

    def _custom_body(self, custom: dict) -> list[dict]:
        out = []
        for name, value in custom.items():
            field = self.custom_fields().get(name.strip().lower())
            if not field or value in (None, ""):
                continue
            kind = field.get("type")
            if kind == "drop_down":  # ClickUp wants the option id, not its label
                option = next((o["id"] for o in (field.get("type_config") or {}).get("options", []) if (o.get("name") or o.get("label") or "").strip().lower() == str(value).strip().lower()), None)
                if option:
                    out.append({"id": field["id"], "value": option})
            elif kind == "date":
                moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                # time=True keeps the moment (a date-only field is shown a day late in some time zones: "Tomorrow" for mail that arrived tonight)
                out.append({"id": field["id"], "value": int((moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).timestamp() * 1000), "value_options": {"time": True}})
            elif kind == "checkbox":
                out.append({"id": field["id"], "value": bool(value)})
            else:  # url, email, short_text, text
                out.append({"id": field["id"], "value": str(value)[:2000]})
        return out

    # ------------------------------------------------------------------ writes (never auto-retried)

    def create_task(self, fields: dict) -> dict:
        body = self._body(fields)
        if fields.get("custom"):
            body["custom_fields"] = self._custom_body(fields["custom"])  # a read: if it fails nothing was written yet
        if fields.get("assignee_id"):
            body["assignees"] = [int(fields["assignee_id"])]
        try:
            return self._norm(self._call("POST", f"/list/{self.list_id}/task", body, safe_to_retry=False))
        except AdapterError as err:
            # The free ClickUp plan caps custom-field usage. A definitive 4xx about custom fields means nothing was created, so creating the task
            # without them cannot duplicate it: the task matters more than its columns. The caller is told the columns were skipped.
            if body.get("custom_fields") and 400 <= int(err.code.removeprefix("clickup_") or 0) < 500 and "custom field" in str(err).lower():
                plain = {k: v for k, v in body.items() if k != "custom_fields"}
                task = self._norm(self._call("POST", f"/list/{self.list_id}/task", plain, safe_to_retry=False))
                task["custom_skipped"] = str(err)[:120]
                return task
            raise

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
    def _custom_values(task: dict) -> dict:
        out: dict = {}
        for f in task.get("custom_fields", []):
            value = f.get("value")
            if value in (None, ""):
                continue
            if f.get("type") == "drop_down":
                options = (f.get("type_config") or {}).get("options", [])
                value = next((o.get("name") for o in options if o.get("orderindex") == value or o.get("id") == value), value)
            elif f.get("type") == "date":
                value = datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
            out[f["name"]] = value
        return out

    @staticmethod
    def _norm(task: dict) -> dict:
        due = task.get("due_date")
        return {"custom": ClickUpAdapter._custom_values(task),
            "id": str(task["id"]), "name": task.get("name", ""), "description": task.get("description") or task.get("text_content") or "",
            "url": task.get("url", ""), "status": (task.get("status") or {}).get("status", ""),
            "assignees": [a.get("username") or a.get("email", "") for a in task.get("assignees", [])],
            "assignee_ids": [str(a.get("id")) for a in task.get("assignees", [])],
            "priority": (task.get("priority") or {}).get("priority"),
            "due_date": datetime.fromtimestamp(int(due) / 1000, tz=timezone.utc).date().isoformat() if due else None,
        }
