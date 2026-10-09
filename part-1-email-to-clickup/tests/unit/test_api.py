"""The API Lambda handler with API-Gateway-shaped events (MOCK adapters). Identity comes only from the Cognito claims."""

import json

import pytest

from helpers import ScriptedTriager, create_triage, make_email
from inbox import api
from inbox.models import Action, Triage
from inbox.adapters.base import AdapterError


def event(method, resource, groups="inbox-reviewers", body=None, path=None, sub="user-1"):
    claims = {"sub": sub, "email": "rev@medgan.ai", "cognito:groups": groups} if sub else {}
    return {"httpMethod": method, "resource": resource, "pathParameters": path, "body": json.dumps(body) if body is not None else None, "requestContext": {"authorizer": {"claims": claims}}}


def call(world, *args, **kw):
    out = api.handler(event(*args, **kw), None, service=world.svc, invoke_async=lambda p: world.async_calls.append(p))
    return out["statusCode"], json.loads(out["body"])


@pytest.fixture()
def w(world):
    world.async_calls = []
    world.triager.script["p-1"] = Triage(action=Action.HUMAN_REVIEW, confidence=0.3, missing_fields=["assignee"])
    world.svc.process(make_email("p-1"))
    return world


def test_group_claim_parsing():
    assert api.principal_from(event("GET", "/x", groups="[inbox-reviewers other]")).groups == ["inbox-reviewers", "other"]
    assert api.principal_from(event("GET", "/x", groups="a,b")).groups == ["a", "b"]
    assert api.principal_from(event("GET", "/x", sub=None)) is None


def test_listing_and_detail(w):
    status, body = call(w, "GET", "/inbox/messages")
    assert status == 200 and body["messages"][0]["message_id"] == "p-1" and body["mode"] == {"outlook": "sample", "clickup": "sample"}
    status, body = call(w, "GET", "/inbox/messages/{id}", path={"id": "p-1"})
    assert status == 200 and body["proposal"]["action"] == "HUMAN_REVIEW" and body["audit"]
    assert call(w, "GET", "/inbox/messages/{id}", path={"id": "nope"})[0] == 404
    assert call(w, "GET", "/inbox/review")[1]["items"][0]["message_id"] == "p-1"
    assert call(w, "GET", "/inbox/activity")[1]["events"]
    assert call(w, "GET", "/inbox/config")[1]["policy"]["auto_send_replies"] is False


def test_unauthenticated_and_unauthorized(w):
    assert call(w, "GET", "/inbox/messages", sub=None)[0] == 401
    for method, resource, body in (("POST", "/inbox/review/{id}/approve", None), ("POST", "/inbox/review/{id}/reject", {"reason": "x"}), ("POST", "/inbox/review/{id}/edit", {}), ("POST", "/inbox/messages/{id}/retry", None)):
        status, out = call(w, method, resource, groups="", body=body, path={"id": "p-1"})
        assert status == 403 and out["error"]["code"] == "forbidden"
    assert call(w, "POST", "/inbox/sync", groups="")[0] == 403 and w.async_calls == []
    for route, path in (("/inbox/messages", None), ("/inbox/messages/{id}", {"id": "p-1"}), ("/inbox/review", None), ("/inbox/activity", None), ("/inbox/config", None)):
        status, out = call(w, "GET", route, groups="some-other-group", path=path)
        assert status == 403 and "body_excerpt" not in json.dumps(out), route  # reads need the reviewer group too
    assert w.store.get("p-1")["status"] == "PENDING_REVIEW"


def test_a_client_supplied_approval_flag_is_ignored(w):
    w.triager.script["p-2"] = create_triage(title="Prepare the audit pack")  # missing assignee: cannot be approved
    w.svc.process(make_email("p-2", day=6))
    status, out = call(w, "POST", "/inbox/review/{id}/approve", body={"approved": True, "force": True, "status": "EXECUTED"}, path={"id": "p-2"})
    assert status == 422 and "missing assignee" in out["error"]["problems"] and w.tasks.created == []


def test_approve_reject_edit_and_conflict_codes(w):
    status, out = call(w, "POST", "/inbox/review/{id}/reject", body={"reason": "duplicate"}, path={"id": "p-1"})
    assert status == 200 and out["status"] == "REJECTED"
    assert call(w, "POST", "/inbox/review/{id}/approve", path={"id": "p-1"})[0] == 409
    assert call(w, "POST", "/inbox/review/{id}/approve", path={"id": "ghost"})[0] == 404
    w.triager.script["p-3"] = create_triage(title="Prepare the audit pack")
    w.svc.process(make_email("p-3", day=6))
    status, out = call(w, "POST", "/inbox/review/{id}/edit", body={"task": {"assignee": "Sara Nasser"}}, path={"id": "p-3"})
    assert status == 200 and out["status"] == "EXECUTED" and w.tasks.created[0]["assignees"] == ["Sara Nasser"]


def test_bad_requests_and_unknown_routes(w):
    bad = api.handler({**event("POST", "/inbox/review/{id}/reject", path={"id": "p-1"}), "body": "{not json"}, None, service=w.svc)
    assert bad["statusCode"] == 400
    big = api.handler({**event("POST", "/inbox/review/{id}/reject", path={"id": "p-1"}), "body": "x" * 30000}, None, service=w.svc)
    assert big["statusCode"] == 400
    assert call(w, "DELETE", "/inbox/messages/{id}", path={"id": "p-1"})[0] == 404


def test_sync_is_asynchronous_and_guards_against_overlap(w):
    status, out = call(w, "POST", "/inbox/sync")
    assert status == 202 and out["state"] == "running" and len(w.async_calls) == 1
    status, out = call(w, "POST", "/inbox/sync")
    assert status == 202 and out.get("already_running") and len(w.async_calls) == 1  # no second worker while one runs


def test_the_worker_processes_the_mailbox_and_records_the_result(w):
    for i in range(3):
        w.mail.add(make_email(f"s-{i}", day=5 + i))
    call(w, "POST", "/inbox/sync")
    summary = api.handler(w.async_calls[0], None, service=w.svc)
    assert summary["new"] == 3 + 0 and w.store.get_meta("sync")["state"] == "done"
    assert call(w, "GET", "/inbox/messages")[1]["sync"]["new"] == 3


def test_worker_rejects_a_forged_payload_and_reports_mailbox_failures(w):
    with pytest.raises(Exception):
        api.handler({"job": "sync", "principal": {"user_id": "x", "groups": []}}, None, service=w.svc)
    w.mail.fail_next("list_recent_emails", "graph_503", retryable=True)
    call(w, "POST", "/inbox/sync")
    out = api.handler(w.async_calls[0], None, service=w.svc)
    assert out == {"error": "graph_503"} and w.store.get_meta("sync")["state"] == "failed"


def test_integration_errors_are_502_and_internal_errors_leak_nothing(w, monkeypatch):
    monkeypatch.setattr(w.svc, "list_messages", lambda *a, **k: (_ for _ in ()).throw(AdapterError("clickup_503", "down", retryable=True)))
    status, out = call(w, "GET", "/inbox/messages")
    assert status == 502 and out["error"]["retryable"] is True
    monkeypatch.setattr(w.svc, "list_activity", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secret internals")))
    status, out = call(w, "GET", "/inbox/activity")
    assert status == 500 and "secret" not in json.dumps(out)


def test_review_items_say_whether_they_can_be_approved_and_why_not(w):
    w.triager.script["p-9"] = create_triage(title="Prepare the audit pack")
    w.svc.process(make_email("p-9", day=6))
    view = call(w, "GET", "/inbox/messages/{id}", path={"id": "p-9"})[1]
    assert view["can_approve"] is False and "missing assignee" in view["problems"]
    cfg = call(w, "GET", "/inbox/config")[1]
    assert [m["name"] for m in cfg["members"]] == ["Mohammed Zaloom", "Ahmad Haddad", "Sara Nasser"] and "to do" in cfg["statuses"]
    call(w, "POST", "/inbox/review/{id}/edit", body={"task": {"assignee": "Sara Nasser"}}, path={"id": "p-9"})
    assert call(w, "GET", "/inbox/messages/{id}", path={"id": "p-9"})[1]["can_approve"] is False  # executed now: nothing left to approve
