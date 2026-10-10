"""THE DEMO SCENARIO, automated, on the real deployed stack: real Microsoft Graph mailbox (xpand@medgan.ai), real webhook, real agent on AgentCore, real
ClickUp list, real Cognito reviewer. Skips itself unless the stack runs with OUTLOOK_MODE=graph.

The test sends itself emails as xpand@medgan.ai (Graph sendMail), waits for the webhook to deliver them, then acts as the reviewer through the API:
  1. a "please confirm" email -> a REPLY proposal with a real draft in Outlook -> Approve -> the DRAFT is sent (no orphan) and arrives
  2. another one -> Reject -> the draft is deleted and nothing is sent
  3. a "create a task" email -> a ClickUp task with assignee, priority, due date and the list's custom fields (sender, received date, Outlook link, Inbox Action)
Everything it creates (mail, table rows, ClickUp tasks) is removed afterwards, so the demo mailbox stays clean. Run: make test-demo
"""

import json
import time
import urllib.parse
import uuid
from datetime import date, timedelta

import boto3
import pytest
from botocore.exceptions import ClientError

from test_deployed_inbox import REGION, call, cfg, clickup, reviewer  # noqa: F401  (fixtures)

pytestmark = pytest.mark.e2e
MAILBOX = "xpand@medgan.ai"
TAG = f"E2E-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def graph():
    from inbox.adapters.graph import GraphAdapter, SecretsManagerBox

    return GraphAdapter(SecretsManagerBox("xpand/inbox/graph", REGION))


@pytest.fixture(scope="module")
def real(cfg, reviewer):
    mode = call(cfg, "GET", "/inbox/config", reviewer)[2]
    if mode["outlook_mode"] != "graph" or mode["webhook"]["state"] != "active":
        pytest.skip("needs the real mailbox with live updates on")


def send_to_self(graph, subject, body):
    graph._call("POST", "/me/sendMail", {"message": {"subject": subject, "body": {"contentType": "Text", "content": body}, "toRecipients": [{"emailAddress": {"address": MAILBOX}}]}, "saveToSentItems": False}, safe_to_retry=False)


def find_item(cfg, reviewer, subject, wait=150, allow_manual_sync_after=None):
    """Waits for the item to show up in the inbox listing. By default ONLY the webhook can deliver it (that is what is being proven)."""
    start, synced = time.time(), False
    while time.time() - start < wait:
        for m in call(cfg, "GET", "/inbox/messages", reviewer)[2].get("messages", []):
            if m["subject"] == subject and m["status"] not in ("PROCESSING",):
                return m
        if allow_manual_sync_after is not None and not synced and time.time() - start > allow_manual_sync_after:
            call(cfg, "POST", "/inbox/sync", reviewer, {}); synced = True
        time.sleep(4)
    raise AssertionError(f"'{subject}' did not arrive within {wait}s")


def detail(cfg, reviewer, mid):
    return call(cfg, "GET", f"/inbox/messages/{urllib.parse.quote(mid, safe='')}", reviewer)[2]


def drafts_for(graph, subject):
    flt = urllib.parse.quote(f"subject eq 'RE: {subject}'", safe="")
    return graph._call("GET", f"/me/mailFolders/drafts/messages?$filter={flt}&$select=id", safe_to_retry=True).get("value", [])


def no_draft_left(graph, subject, wait=45):
    """Graph moves a sent draft out of Drafts asynchronously, so wait for the folder to settle instead of checking once."""
    deadline = time.time() + wait
    while time.time() < deadline:
        if not drafts_for(graph, subject):
            return True
        time.sleep(3)
    return False


def sent_replies(graph, subject):
    flt = urllib.parse.quote(f"subject eq 'RE: {subject}'", safe="")
    return graph._call("GET", f"/me/mailFolders/sentitems/messages?$filter={flt}&$select=id", safe_to_retry=True).get("value", [])


@pytest.fixture(scope="module", autouse=True)
def cleanup(cfg, reviewer, graph, clickup):
    created_tasks: list[str] = []
    clickup.created = created_tasks
    yield
    time.sleep(15)  # replies we send come back into the inbox and may still be in flight
    for task_id in created_tasks:
        try:
            from inbox.adapters.base import http_json
            from inbox.adapters.clickup import API

            secret = json.loads(boto3.client("secretsmanager", region_name=REGION).get_secret_value(SecretId="xpand/inbox/clickup")["SecretString"])
            http_json("DELETE", f"{API}/task/{task_id}", {"Authorization": secret["token"]})
        except Exception:  # noqa: BLE001
            pass
    table = boto3.resource("dynamodb", region_name=REGION).Table(cfg["table"])
    ids = [m["message_id"] for m in call(cfg, "GET", "/inbox/messages", reviewer)[2].get("messages", []) if TAG in m["subject"]]
    for folder in ("inbox", "sentitems", "drafts", "deleteditems"):  # removes our test mail, including the replies and anything still in drafts
        flt = urllib.parse.quote(f"contains(subject,'{TAG}')", safe="")
        try:
            for m in graph._call("GET", f"/me/mailFolders/{folder}/messages?$filter={flt}&$select=id&$top=50", safe_to_retry=True).get("value", []):
                graph._call("DELETE", f"/me/messages/{m['id']}", safe_to_retry=False)
        except Exception:  # noqa: BLE001
            pass
    for page in table.meta.client.get_paginator("scan").paginate(TableName=table.name, ProjectionExpression="pk, sk"):
        for item in page["Items"]:
            if any(item["pk"] == f"MSG#{i}" for i in ids):
                try:
                    table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
                except ClientError:
                    pass


def test_1_a_real_email_arrives_by_webhook_and_an_approved_reply_sends_the_draft(real, cfg, reviewer, graph):
    subject = f"{TAG} please confirm receipt"
    send_to_self(graph, subject, "Hi, can you confirm you received this message? A short reply is enough. Thanks.")
    item = find_item(cfg, reviewer, subject)  # no manual sync: the webhook must deliver it
    assert item["status"] == "PENDING_REVIEW" and item["action"] == "REPLY"
    d = detail(cfg, reviewer, item["message_id"])
    draft_id = d["draft"]["draft_id"]
    assert d["can_approve"] and d["proposal"]["triage"]["reply"]["body"].strip() and d["web_link"].startswith("https://outlook.")
    assert len(drafts_for(graph, subject)) == 1 and sent_replies(graph, subject) == []  # a draft exists, nothing sent yet
    status, _, out = call(cfg, "POST", f"/inbox/review/{urllib.parse.quote(item['message_id'], safe='')}/approve", reviewer, {})
    assert status == 200 and out["status"] == "EXECUTED" and out["sent"] is True
    assert no_draft_left(graph, subject)  # the draft itself was sent: no orphan left in Drafts
    assert len(sent_replies(graph, subject)) == 1  # exactly one reply went out
    assert call(cfg, "POST", f"/inbox/review/{urllib.parse.quote(item['message_id'], safe='')}/approve", reviewer, {})[0] == 409  # never twice


def test_2_a_rejected_reply_deletes_its_draft_and_sends_nothing(real, cfg, reviewer, graph):
    subject = f"{TAG} please confirm the meeting time"
    send_to_self(graph, subject, "Hi, can you confirm the time of the planning meeting next week? A short reply is enough. Thanks.")
    item = find_item(cfg, reviewer, subject, allow_manual_sync_after=60)
    assert item["status"] == "PENDING_REVIEW" and item["action"] == "REPLY"
    assert detail(cfg, reviewer, item["message_id"])["draft"]["draft_id"] and len(drafts_for(graph, subject)) == 1
    status, _, out = call(cfg, "POST", f"/inbox/review/{urllib.parse.quote(item['message_id'], safe='')}/reject", reviewer, {"reason": "e2e: not needed"})
    assert status == 200 and out["status"] == "REJECTED"
    assert no_draft_left(graph, subject) and sent_replies(graph, subject) == []
    events = [a["event"] for a in call(cfg, "GET", "/inbox/activity", reviewer)[2]["events"] if a.get("message_id") == item["message_id"]]
    assert "draft_discarded" in events and "rejected" in events


def test_3_a_task_email_creates_a_clickup_task_with_the_list_custom_fields(real, cfg, reviewer, graph, clickup):
    subject = f"{TAG} create a task"
    due = (date.today() + timedelta(days=30)).isoformat()
    send_to_self(graph, subject, f"Please create a task: organise the team offsite {TAG}. Assign it to Xpand Assessment, high priority, due {due}. Description: book the venue and send the invitations for the team offsite {TAG}.")
    item = find_item(cfg, reviewer, subject, allow_manual_sync_after=60)
    assert item["action"] == "CREATE_TASK"
    if item["status"] == "PENDING_REVIEW":  # a person approves anything the policy did not auto-run
        status, _, out = call(cfg, "POST", f"/inbox/review/{urllib.parse.quote(item['message_id'], safe='')}/approve", reviewer, {})
        assert status == 200 and out["status"] == "EXECUTED"
    d = detail(cfg, reviewer, item["message_id"])
    assert d["status"] == "EXECUTED" and d["execution"]["task_id"]
    clickup.created.append(d["execution"]["task_id"])
    task = clickup.a.get_task(d["execution"]["task_id"])
    assert task["assignees"] == ["Xpand Assessment"] and task["priority"] == "high" and task["due_date"] == due and task["status"] == "to do"
    custom = task["custom"]
    assert custom["Sender Email Address"] == MAILBOX and custom["Inbox Action"] == "Route" and custom["Message Received Date"].startswith(date.today().isoformat()[:7])
    assert custom["Source Message Link"].startswith("https://outlook.") and f"[email:{item['message_id']}]" in task["description"]
    # a second delivery of the same email changes nothing
    tasks_before = len(clickup.a.list_tasks())
    call(cfg, "POST", "/inbox/sync", reviewer, {})
    time.sleep(20)
    assert len(clickup.a.list_tasks()) == tasks_before
