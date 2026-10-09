"""The two narrow integration surfaces. Everything outside this package talks to ClickUp and Outlook only through these."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any, Callable, Optional, Protocol

from ..models import Email, Member


class AdapterError(Exception):
    """An integration failed. `retryable` is True only for timeouts, throttling and 5xx: never for a rejected request."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.retryable = code, retryable


class TaskAdapter(Protocol):
    mode: str

    def list_members(self) -> list[Member]: ...
    def list_statuses(self) -> list[str]: ...
    def list_tasks(self) -> list[dict]: ...  # normalised: id, name, description, url, status, assignees, priority, due_date
    def get_task(self, task_id: str) -> dict: ...
    def create_task(self, fields: dict) -> dict: ...  # fields: name, description, assignee_id, priority(int), due_date(date), status
    def update_task(self, task_id: str, fields: dict) -> dict: ...


class MailAdapter(Protocol):
    mode: str

    def list_recent_emails(self, limit: int = 25) -> list[Email]: ...
    def get_email(self, message_id: str) -> Email: ...
    def draft_reply(self, message_id: str, body: str) -> dict: ...  # {"draft_id": ...}; never sends
    def send_reply(self, message_id: str, body: str) -> dict: ...  # sends; the service calls it only after approval


def http_form(url: str, data: dict, timeout: float = 15.0) -> tuple[int, Any]:
    """POST application/x-www-form-urlencoded (the OAuth token endpoint's format)."""
    import urllib.parse

    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST", headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"{}")
        except ValueError:
            return err.code, {}
    except (socket.timeout, TimeoutError):
        raise AdapterError("timeout", "the sign-in service did not answer in time", retryable=True) from None
    except urllib.error.URLError as err:
        raise AdapterError("network", f"could not reach the sign-in service: {type(err.reason).__name__}", retryable=True) from None


HttpFn = Callable[[str, str, dict, Optional[dict], float], tuple[int, Any]]


def http_json(method: str, url: str, headers: dict, body: Optional[dict] = None, timeout: float = 15.0) -> tuple[int, Any]:
    """Minimal JSON-over-HTTPS client (urllib, no extra dependency). Returns (status, parsed body); network failures raise AdapterError."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", "Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw) if raw else {}
        except ValueError:
            return err.code, {"raw": raw[:200].decode("utf-8", "replace")}
    except (socket.timeout, TimeoutError):
        raise AdapterError("timeout", "the service did not answer in time", retryable=True) from None
    except urllib.error.URLError as err:
        raise AdapterError("network", f"could not reach the service: {type(err.reason).__name__}", retryable=True) from None
