"""Lambda behind API Gateway (Cognito authorizer): the Inbox Automation backend API.

Caller identity and groups come from the verified Cognito claims in the request context, never from the body. Every state-changing route
is authorised by the service (reviewer group) and enforced by conditional writes. Sync runs as an asynchronous worker invocation because
API Gateway answers within 29 seconds and triaging real mail takes longer.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

from .adapters.base import AdapterError
from .agent import AgentRuntimeTriager
from .config import Settings
from .models import Principal
from .service import Conflict, Forbidden, InboxService, Invalid, NotFound
from .store import iso, utcnow
from .wiring import build_service

log = logging.getLogger("inbox.api")
MAX_BODY = 20_000
_service: Optional[InboxService] = None


def principal_from(event: dict) -> Optional[Principal]:
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("claims")) or {}
    if not claims.get("sub"):
        return None
    raw = claims.get("cognito:groups", "")
    groups = [g for g in raw.strip("[]").replace(",", " ").split() if g] if isinstance(raw, str) else list(raw or [])
    return Principal(user_id=claims["sub"], email=claims.get("email", ""), groups=groups)


def _service_instance() -> InboxService:
    global _service
    if _service is None:
        settings = Settings.from_env()
        _service = build_service(settings, AgentRuntimeTriager(settings))
    return _service


def _response(status: int, body: Any) -> dict:
    return {"statusCode": status, "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN", "*"), "Vary": "Origin", "Cache-Control": "no-store"}, "body": json.dumps(body, default=str)}


def _error(status: int, code: str, message: str, **extra: Any) -> dict:
    return _response(status, {"error": {"code": code, "message": message, **extra}})


def handler(event: dict, context: Any = None, service: Optional[InboxService] = None, invoke_async: Optional[Callable[[dict], None]] = None) -> dict:
    svc = service or _service_instance()
    if event.get("job") == "sync":  # asynchronous worker invocation (not reachable from API Gateway)
        return _run_sync(svc, event)
    principal = principal_from(event)
    method, resource = event.get("httpMethod", ""), event.get("resource", "")
    params = event.get("pathParameters") or {}
    try:
        body = _body(event)
        if principal is None:
            return _error(401, "unauthenticated", "Sign in again.")
        svc._require_reviewer(principal)  # reads expose email text and the audit trail, so they need the reviewer group too
        if resource == "/inbox/config" and method == "GET":
            return _response(200, _config(svc))
        if resource == "/inbox/messages" and method == "GET":
            return _response(200, {"messages": svc.list_messages(), "sync": svc.store.get_meta("sync"), "mode": {"outlook": svc.mail.mode, "clickup": svc.tasks.mode}})
        if resource == "/inbox/messages/{id}" and method == "GET":
            return _response(200, svc.message_view(params["id"]))
        if resource == "/inbox/review" and method == "GET":
            return _response(200, {"items": svc.list_review()})
        if resource == "/inbox/activity" and method == "GET":
            return _response(200, {"events": svc.list_activity()})
        if resource == "/inbox/sync" and method == "POST":
            return _start_sync(svc, principal, invoke_async)
        if resource == "/inbox/review/{id}/approve" and method == "POST":
            return _response(200, svc.approve(params["id"], principal))
        if resource == "/inbox/review/{id}/reject" and method == "POST":
            return _response(200, svc.reject(params["id"], principal, str(body.get("reason", ""))))
        if resource == "/inbox/review/{id}/edit" and method == "POST":
            return _response(200, svc.edit(params["id"], principal, body))
        if resource == "/inbox/messages/{id}/retry" and method == "POST":
            return _response(200, svc.retry(params["id"], principal))
        return _error(404, "not_found", "Unknown route.")
    except Forbidden as err:
        return _error(403, "forbidden", str(err))
    except NotFound:
        return _error(404, "not_found", "Not found.")
    except Conflict as err:
        return _error(409, "conflict", str(err))
    except Invalid as err:
        return _error(422, "invalid", "The proposal cannot run yet.", problems=err.problems)
    except _BadRequest as err:
        return _error(400, "bad_request", str(err))
    except AdapterError as err:
        log.warning("integration failed", extra={"code": err.code})
        return _error(502, err.code, str(err), retryable=err.retryable)
    except Exception:  # never leak internals
        log.exception("unhandled error")
        return _error(500, "internal", "Something went wrong.")


class _BadRequest(Exception):
    pass


def _body(event: dict) -> dict:
    raw = event.get("body")
    if not raw:
        return {}
    if len(raw) > MAX_BODY:
        raise _BadRequest("request body too large")
    try:
        value = json.loads(raw)
    except ValueError:
        raise _BadRequest("body must be JSON") from None
    if not isinstance(value, dict):
        raise _BadRequest("body must be a JSON object")
    return value


def _config(svc: InboxService) -> dict:
    p = svc.settings.policy
    try:  # the edit form needs real ClickUp values; a ClickUp outage must not break the page
        members = [{"id": m.id, "name": m.username or m.email, "email": m.email} for m in svc.tasks.list_members()]
        statuses = svc.tasks.list_statuses()
    except AdapterError:
        members, statuses = [], []
    return {"members": members, "statuses": statuses, "clickup_list_url": getattr(svc.tasks, "list_url", None), "mailbox": svc.settings.mailbox, "outlook_mode": svc.mail.mode, "clickup_mode": svc.tasks.mode, "reviewer_group": svc.settings.reviewer_group,
            "policy": {"auto_send_replies": p.auto_send_replies, "min_confidence": p.min_confidence, "duplicate_high": p.duplicate_high, "duplicate_low": p.duplicate_low,
                       "default_priority": p.default_priority, "default_status": p.default_status, "required_for_create": list(p.required_for_create)}}


def _start_sync(svc: InboxService, principal: Principal, invoke_async: Optional[Callable[[dict], None]]) -> dict:
    svc._require_reviewer(principal)
    current = svc.store.get_meta("sync") or {}
    if current.get("state") == "running" and current.get("lease_until", "") > iso(utcnow()):
        return _response(202, {**current, "already_running": True})
    meta = {"state": "running", "started_at": iso(utcnow()), "lease_until": iso(utcnow().replace(microsecond=0) + __import__("datetime").timedelta(minutes=10)), "requested_by": principal.email or principal.user_id}
    svc.store.put_meta("sync", meta)
    (invoke_async or _invoke_self)({"job": "sync", "principal": principal.model_dump()})
    return _response(202, meta)


def _invoke_self(payload: dict) -> None:
    import boto3

    boto3.client("lambda").invoke(FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"], InvocationType="Event", Payload=json.dumps(payload).encode())


def _run_sync(svc: InboxService, event: dict) -> dict:
    principal = Principal.model_validate(event["principal"])
    svc._require_reviewer(principal)  # re-checked in the worker: the payload is not trusted just because it arrived
    started = (svc.store.get_meta("sync") or {}).get("started_at", iso(utcnow()))
    try:
        emails = svc.mail.list_recent_emails(svc.settings.sync_limit)
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(svc.process, emails))
        summary = {"fetched": len(emails), "new": sum(o["outcome"] == "processed" for o in outcomes), "duplicates": sum(o["outcome"] == "duplicate" for o in outcomes), "failed": sum(o["outcome"] == "failed" for o in outcomes)}
        svc.store.put_meta("sync", {"state": "done", "started_at": started, "finished_at": iso(utcnow()), **summary, "requested_by": principal.email})
        svc._audit("-", "sync", principal, outcome="ok", detail=f"{summary['new']} new, {summary['duplicates']} already known, {summary['failed']} failed")
        return summary
    except Exception as err:
        code = getattr(err, "code", type(err).__name__)
        svc.store.put_meta("sync", {"state": "failed", "started_at": started, "finished_at": iso(utcnow()), "error": str(code), "requested_by": principal.email})
        svc._audit("-", "sync_failed", principal, outcome="failed", detail=str(code))
        return {"error": str(code)}
