"""The DEPLOYED Inbox Automation API with real Cognito tokens, real Amazon Bedrock (AgentCore runtime + gateway), real DynamoDB and the REAL
ClickUp list. Two modes, chosen by how the stack is deployed (`INBOX_OUTLOOK_MODE`):
- sample: the 8-email pipeline scenario runs against the labelled sample mailbox.
- graph: the real mailbox xpand@medgan.ai; the pipeline scenario is skipped (it must never act on real mail) and the real-mailbox and webhook checks run.
Tests never touch rows of real emails or the webhook subscription: only `MSG#sample-*` rows are reset.

Needs AWS credentials (profile with cognito-idp admin and secretsmanager read), build/outputs.json and .demo-credentials.
Everything created in ClickUp is deleted afterwards; the temporary non-reviewer Cognito user is deleted too."""

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import boto3
import pytest

pytestmark = pytest.mark.e2e
ROOT = Path(__file__).resolve().parents[3] / "part-2-data-to-answers"
ORIGIN = "https://xpand.medgan.ai"
REGION = "us-east-1"


@pytest.fixture(scope="module")
def cfg():
    outputs = next(iter(json.loads((ROOT / "build" / "outputs.json").read_text()).values()))
    creds = dict(line.strip().split("=", 1) for line in (ROOT / ".demo-credentials").read_text().splitlines() if "=" in line)
    return {"api": outputs["ApiUrl"].rstrip("/"), "pool": outputs["UserPoolId"], "client": outputs["UserPoolClientId"], "email": creds["email"], "password": creds["password"], "table": [v for k, v in outputs.items() if "InboxTableName" in k][0]}


def token_for(cfg, email, password):
    cog = boto3.client("cognito-idp", region_name=REGION)
    return cog.admin_initiate_auth(UserPoolId=cfg["pool"], ClientId=cfg["client"], AuthFlow="ADMIN_USER_PASSWORD_AUTH", AuthParameters={"USERNAME": email, "PASSWORD": password})["AuthenticationResult"]["IdToken"]


@pytest.fixture(scope="module")
def reviewer(cfg):
    return token_for(cfg, cfg["email"], cfg["password"])


@pytest.fixture(scope="module")
def outsider(cfg):
    """A real Cognito user who is NOT in the inbox-reviewers group."""
    cog = boto3.client("cognito-idp", region_name=REGION)
    email, password = f"outsider-{uuid.uuid4().hex[:8]}@xpandpros.com", "Outs1der-Passw0rd!x"
    cog.admin_create_user(UserPoolId=cfg["pool"], Username=email, UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}], MessageAction="SUPPRESS")
    cog.admin_set_user_password(UserPoolId=cfg["pool"], Username=email, Password=password, Permanent=True)
    yield token_for(cfg, email, password)
    cog.admin_delete_user(UserPoolId=cfg["pool"], Username=email)


@pytest.fixture(scope="module")
def clickup():
    from inbox.adapters.clickup import API, ClickUpAdapter
    from inbox.adapters.base import http_json

    secret = json.loads(boto3.client("secretsmanager", region_name=REGION).get_secret_value(SecretId="xpand/inbox/clickup")["SecretString"])
    adapter = ClickUpAdapter.from_secret(secret)
    seeded = []
    yield type("CU", (), {"a": adapter, "seeded": seeded})()
    for task in adapter.list_tasks():  # remove everything this run created: seeded tasks and tasks the pipeline created from sample emails
        if task["id"] in seeded or "[email:sample-" in task["description"]:
            http_json("DELETE", f"{API}/task/{task['id']}", {"Authorization": secret["token"]})


def _reset(table):
    """Starts and ends without sample-mailbox rows so reruns are comparable. Rows of real emails and the webhook subscription are never touched."""
    for page in table.meta.client.get_paginator("scan").paginate(TableName=table.name, ProjectionExpression="pk, sk"):
        for item in page["Items"]:
            if not str(item["pk"]["S"] if isinstance(item["pk"], dict) else item["pk"]).startswith("MSG#sample-"):
                continue
            table.delete_item(Key={"pk": item["pk"]["S"] if isinstance(item["pk"], dict) else item["pk"], "sk": item["sk"]["S"] if isinstance(item["sk"], dict) else item["sk"]})


@pytest.fixture(scope="module")
def table(cfg):
    t = boto3.resource("dynamodb", region_name=REGION).Table(cfg["table"])
    _reset(t)
    yield t
    _reset(t)


def call(cfg, method, path, token=None, body=None):
    headers = {"Content-Type": "application/json", "Origin": ORIGIN}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(cfg["api"] + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, dict(r.headers), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, dict(err.headers), json.loads(raw or b"{}")
        except ValueError:
            return err.code, dict(err.headers), {"raw": raw.decode()[:200]}


def wait_for_sync(cfg, token, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, _, body = call(cfg, "GET", "/inbox/messages", token)
        sync = body.get("sync") or {}
        if sync.get("state") in ("done", "failed"):
            return body
        time.sleep(4)
    raise AssertionError("sync did not finish in time")


# ------------------------------------------------------------------ access control (10)
def test_unauthenticated_and_non_reviewers_are_refused_everywhere(cfg, outsider):
    for method, path in (("GET", "/inbox/config"), ("GET", "/inbox/messages"), ("GET", "/inbox/review"), ("GET", "/inbox/activity"), ("POST", "/inbox/sync")):
        assert call(cfg, method, path)[0] == 401, path
        status, _, body = call(cfg, method, path, outsider, {} if method == "POST" else None)
        assert status == 403 and "body_excerpt" not in json.dumps(body), path
    for path in ("/inbox/review/x/approve", "/inbox/review/x/reject", "/inbox/review/x/edit", "/inbox/messages/x/retry"):
        assert call(cfg, "POST", path, outsider, {})[0] == 403, path
    assert call(cfg, "GET", "/inbox/messages", "not.a.jwt")[0] == 401


def test_cors_headers_on_denials(cfg, outsider):
    _, headers, _ = call(cfg, "GET", "/inbox/messages", outsider)
    assert headers.get("Access-Control-Allow-Origin") == ORIGIN


# ------------------------------------------------------------------ full pipeline on the deployed stack (1 to 8, 11)
def test_deployed_pipeline(cfg, reviewer, outsider, clickup, table):
    if call(cfg, "GET", "/inbox/config", reviewer)[2]["outlook_mode"] != "sample":
        pytest.skip("the 8-email scenario needs the sample mailbox; this stack reads the real mailbox")
    seed = clickup.a.create_task({"name": "Prepare the Q3 marketing report", "description": "Seed task for the deployed update scenario", "assignee_id": "246097569", "priority": 3, "status": "in progress"})
    clickup.seeded.append(seed["id"])

    status, _, config = call(cfg, "GET", "/inbox/config", reviewer)
    assert status == 200 and config["clickup_mode"] == "api" and config["outlook_mode"] in ("sample", "graph") and [m["name"] for m in config["members"]]

    status, _, started = call(cfg, "POST", "/inbox/sync", reviewer, {})
    assert status == 202 and started["state"] == "running"
    listing = wait_for_sync(cfg, reviewer)
    assert listing["sync"]["state"] == "done", listing["sync"]
    by_subject = {m["subject"]: m for m in listing["messages"]}
    assert len(by_subject) == 8 and listing["sync"]["failed"] == 0

    # 2: informational -> IGNORE, nothing created
    assert by_subject["Re: report"]["status"] in ("IGNORED", "PENDING_REVIEW") and not by_subject["Re: report"]["task_id"]
    # 3: ambiguous -> person
    assert by_subject["Client issue"]["status"] == "PENDING_REVIEW"
    # 1: clear request -> a REAL task with the right fields (or, if the agent hedged, a reviewable proposal and nothing created)
    clear = by_subject["Q4 sales report"]
    if clear["status"] == "EXECUTED":
        task = clickup.a.get_task(clear["task_id"])
        assert task["assignees"] == ["Mohammed Zaloom"] and task["priority"] == "high" and task["due_date"] == "2026-10-25" and task["status"] == "to do" and "[email:sample-001]" in task["description"]
    # 7: sensitive external request -> never executed automatically, never sent
    contract = by_subject["Contract question"]
    assert contract["status"] == "PENDING_REVIEW" and not contract["task_id"]
    # 8: missing fields -> not invented
    _, _, newsletter = call(cfg, "GET", f"/inbox/messages/{by_subject['Newsletter']['message_id']}", reviewer)
    assert newsletter["status"] == "PENDING_REVIEW" and newsletter["can_approve"] is False and any("assignee" in p for p in newsletter["problems"])
    assert newsletter["proposal"]["resolved"]["assignee_id"] is None and newsletter["proposal"]["resolved"]["due_date"] is None
    # 4: the update of existing work changed the seeded real task, and did not create a second one
    update = by_subject["Marketing report moved"]
    after = clickup.a.get_task(seed["id"])
    if update["status"] == "EXECUTED":
        assert after["status"] == "blocked" and after["due_date"] == "2026-10-27"
    else:
        assert update["status"] == "PENDING_REVIEW" and after["status"] == "in progress"
    assert len([t for t in clickup.a.list_tasks() if "Q3 marketing report" in t["name"]]) == 1

    # 5: repeated delivery -> nothing new, no extra tasks
    tasks_before = len(clickup.a.list_tasks())
    call(cfg, "POST", "/inbox/sync", reviewer, {})
    again = wait_for_sync(cfg, reviewer)
    assert again["sync"]["new"] == 0 and again["sync"]["duplicates"] == 8 and len(clickup.a.list_tasks()) == tasks_before

    # approval gate on the real stack: cannot approve a proposal that is not executable; a client "approved" flag changes nothing
    nid = by_subject["Newsletter"]["message_id"]
    status, _, body = call(cfg, "POST", f"/inbox/review/{nid}/approve", reviewer, {"approved": True, "status": "EXECUTED"})
    assert status == 422 and any("assignee" in p for p in body["error"]["problems"]) and len(clickup.a.list_tasks()) == tasks_before
    assert call(cfg, "POST", f"/inbox/review/{nid}/approve", outsider, {})[0] == 403
    assert table.get_item(Key={"pk": f"MSG#{nid}", "sk": "STATE"})["Item"]["status"] == "PENDING_REVIEW"

    # edit + approve with a REAL member: the task is created in ClickUp with the edited values
    status, _, body = call(cfg, "POST", f"/inbox/review/{nid}/edit", reviewer, {"task": {"assignee": "Mohammed Zaloom", "title": "October newsletter", "description": "Prepare the October newsletter"}})
    assert status == 200 and body["status"] == "EXECUTED"
    created = clickup.a.get_task(body["task_id"])
    clickup.seeded.append(created["id"])
    assert created["assignees"] == ["Mohammed Zaloom"] and created["name"] == "October newsletter" and created["status"] == "to do"
    assert call(cfg, "POST", f"/inbox/review/{nid}/approve", reviewer, {})[0] == 409  # second approval: already handled
    assert len([t for t in clickup.a.list_tasks() if t["name"] == "October newsletter"]) == 1

    # 11: rejection executes nothing
    cid = by_subject["Client issue"]["message_id"]
    before = len(clickup.a.list_tasks())
    status, _, body = call(cfg, "POST", f"/inbox/review/{cid}/reject", reviewer, {"reason": "e2e: not needed"})
    assert status == 200 and body["status"] == "REJECTED" and len(clickup.a.list_tasks()) == before
    assert call(cfg, "POST", f"/inbox/review/{cid}/approve", reviewer, {})[0] == 409

    # the reviewer decides an item the agent could not (HUMAN_REVIEW): a reply is only sent because the reviewer chose and approved it
    status, _, body = call(cfg, "POST", f"/inbox/review/{contract['message_id']}/approve", reviewer, {})
    assert status == 422  # an undecided item cannot simply be "approved"
    assert call(cfg, "POST", f"/inbox/review/{contract['message_id']}/edit", outsider, {"action": "REPLY", "reply_body": "x"})[0] == 403
    status, _, body = call(cfg, "POST", f"/inbox/review/{contract['message_id']}/edit", reviewer, {"action": "REPLY", "reply_body": "Thank you. We will confirm the details by email."})
    assert status == 200 and body["status"] == "EXECUTED" and body.get("sent") is True
    status, _, view = call(cfg, "GET", f"/inbox/messages/{contract['message_id']}", reviewer)
    assert view["status"] == "EXECUTED" and view["proposal"]["action"] == "REPLY" and view["approved_by"] == cfg["email"]

    # audit trail exists and records the denied attempts
    _, _, activity = call(cfg, "GET", "/inbox/activity", reviewer)
    events = {e["event"] for e in activity["events"]}
    assert {"received", "triaged", "queued_for_review", "duplicate_delivery", "edited_and_approved", "rejected"} <= events and "unauthorized" in events


def test_real_dynamodb_conditional_writes_are_atomic(cfg):
    """The guarantee moto cannot give under threads: exactly one of many concurrent claims and transitions wins."""
    import threading

    from inbox.models import Status
    from inbox.store import DynamoStore

    store = DynamoStore(cfg["table"], region=REGION)
    mid = f"atomic-{uuid.uuid4().hex[:8]}"
    wins = []
    item = {"status": "PROCESSING", "received_at": "2026-10-09T00:00:00.000Z", "lease_until": "2099-01-01T00:00:00.000Z", "attempts": 1}
    threads = [threading.Thread(target=lambda: wins.append(store.claim(mid, item))) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert wins.count(True) == 1
    store.transition(mid, [Status.PROCESSING], Status.PENDING_REVIEW)
    wins.clear()
    threads = [threading.Thread(target=lambda: wins.append(store.transition(mid, [Status.PENDING_REVIEW], Status.EXECUTING))) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert wins.count(True) == 1
    boto3.resource("dynamodb", region_name=REGION).Table(cfg["table"]).delete_item(Key={"pk": f"MSG#{mid}", "sk": "STATE"})


# ------------------------------------------------------------------ real mailbox and webhook (graph mode)
def test_webhook_endpoint_is_public_but_only_answers_genuine_calls(cfg, reviewer):
    with urllib.request.urlopen(urllib.request.Request(cfg["api"] + "/inbox/webhook?validationToken=Validation%3A%20Testing%20reachability", method="POST", data=b""), timeout=30) as r:
        assert r.status == 200 and r.headers["Content-Type"].startswith("text/plain") and r.read() == b"Validation: Testing reachability"  # echoed as plain text
    sync_before = call(cfg, "GET", "/inbox/messages", reviewer)[2].get("sync")
    for forged in ({"value": [{"clientState": "guess"}]}, {"value": []}, {}):
        assert call(cfg, "POST", "/inbox/webhook", None, forged)[0] == 401
    assert call(cfg, "GET", "/inbox/messages", reviewer)[2].get("sync") == sync_before  # a forged call started nothing
    assert call(cfg, "GET", "/inbox/webhook")[0] in (403, 404)  # only POST exists


def test_real_mailbox_sync_and_live_updates(cfg, reviewer):
    _, _, config = call(cfg, "GET", "/inbox/config", reviewer)
    if config["outlook_mode"] != "graph":
        pytest.skip("this stack uses the sample mailbox")
    assert config["mailbox"] == "xpand@medgan.ai" and config["webhook"]["state"] == "active" and "client_state" not in json.dumps(config["webhook"])
    assert call(cfg, "POST", "/inbox/sync", reviewer, {})[0] == 202
    listing = wait_for_sync(cfg, reviewer)
    assert listing["sync"]["state"] == "done" and listing["sync"]["failed"] == 0 and listing["mode"]["outlook"] == "graph"
    assert not any(m["message_id"].startswith("sample-") for m in listing["messages"])  # a real mailbox never lists sample items (it may legitimately be empty)
