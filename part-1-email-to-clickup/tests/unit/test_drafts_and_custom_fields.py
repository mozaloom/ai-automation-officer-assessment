"""The reply draft lifecycle (draft -> approve sends THAT draft; reject deletes it) and the ClickUp list's custom fields (MOCK adapters and fake HTTP)."""

from datetime import date

import pytest

from helpers import create_triage, make_email
from inbox.adapters.base import AdapterError
from inbox.models import Action, Principal, ReplyDraft, Triage
from inbox.service import Forbidden
from test_adapters_and_rules import adapter
from test_graph import make

REVIEWER = Principal(user_id="u1", email="rev@medgan.ai", groups=["inbox-reviewers"])
FIELDS = {"fields": [
    {"id": "f-date", "name": "Message Received Date", "type": "date"}, {"id": "f-reply", "name": "Reply Required", "type": "checkbox"},
    {"id": "f-act", "name": "Inbox Action", "type": "drop_down", "type_config": {"options": [{"id": "o-reply", "name": "Reply", "orderindex": 0}, {"id": "o-route", "name": "Route", "orderindex": 1}, {"id": "o-esc", "name": "Escalate", "orderindex": 4}]}},
    {"id": "f-link", "name": "Source Message Link", "type": "url"}, {"id": "f-mail", "name": "Sender Email Address", "type": "email"}]}


# ------------------------------------------------------------------ ClickUp custom fields
def test_custom_fields_are_mapped_by_name_to_ids_option_ids_and_epoch_milliseconds():
    cu, http = adapter((200, FIELDS), (200, {"id": "x1", "name": "N", "url": "u", "status": {"status": "to do"}}))
    cu.create_task({"name": "N", "custom": {"Sender Email Address": "layla@medgan.ai", "Message Received Date": "2026-10-09T18:34:40.000Z", "Source Message Link": "https://outlook.office365.com/owa/?ItemID=1",
                                            "Inbox Action": "route", "Reply Required": None, "Unknown Column": "ignored"}})
    (m0, u0, _, _), (m1, u1, _, body) = http.calls
    assert (m0, u0.endswith("/list/L1/field"), m1, u1.endswith("/list/L1/task")) == ("GET", True, "POST", True)
    assert body["custom_fields"] == [{"id": "f-mail", "value": "layla@medgan.ai"}, {"id": "f-date", "value": 1791570880000, "value_options": {"time": True}}, {"id": "f-link", "value": "https://outlook.office365.com/owa/?ItemID=1"}, {"id": "f-act", "value": "o-route"}]


def test_a_field_the_list_does_not_have_or_an_unknown_option_is_skipped_not_invented():
    cu, http = adapter((200, {"fields": [FIELDS["fields"][2]]}), (200, {"id": "x1", "name": "N", "url": "u"}))
    cu.create_task({"name": "N", "custom": {"Inbox Action": "Does Not Exist", "Sender Email Address": "a@b.co"}})
    assert "custom_fields" in http.calls[1][3] and http.calls[1][3]["custom_fields"] == []


def test_the_field_list_is_read_once_and_a_failed_read_writes_nothing():
    cu, http = adapter((200, FIELDS), (200, {"id": "a"}), (200, {"id": "b"}))
    cu.create_task({"name": "A", "custom": {"Inbox Action": "Route"}}); cu.create_task({"name": "B", "custom": {"Inbox Action": "Route"}})
    assert [c[0] for c in http.calls] == ["GET", "POST", "POST"]
    cu, http = adapter(AdapterError("timeout", "slow", retryable=True), (200, {"id": "x"}))
    cu.custom_fields = lambda: (_ for _ in ()).throw(AdapterError("timeout", "slow", retryable=True))
    with pytest.raises(AdapterError):
        cu.create_task({"name": "N", "custom": {"Inbox Action": "Route"}})
    assert not any(c[0] == "POST" for c in http.calls)  # the read failed before any write


def test_task_custom_values_come_back_readable():
    cu, _ = adapter((200, {"id": "x1", "name": "N", "url": "u", "status": {"status": "to do"}, "custom_fields": [
        {"name": "Inbox Action", "type": "drop_down", "value": 1, "type_config": FIELDS["fields"][2]["type_config"]},
        {"name": "Message Received Date", "type": "date", "value": "1791570880000"}, {"name": "Sender Email Address", "type": "email", "value": "a@b.co"}, {"name": "Reply Required", "type": "checkbox", "value": None}]}))
    assert cu.get_task("x1")["custom"] == {"Inbox Action": "Route", "Message Received Date": "2026-10-09T18:34:40+00:00", "Sender Email Address": "a@b.co"}


def test_a_created_task_carries_the_email_facts_and_sensitive_work_is_escalated(world):
    link = "https://outlook.office365.com/owa/?ItemID=Z"
    email = make_email("m-cf", sender="layla@medgan.ai", subject="Report", body="Please prepare the report", day=7).model_copy(update={"web_link": link})
    world.triager.script["m-cf"] = create_triage(title="Order office chairs", description="Order six office chairs.", assignee="Sara Nasser")
    world.svc.process(email)
    (task,) = world.tasks.created
    assert task["custom"] == {"Sender Email Address": "layla@medgan.ai", "Message Received Date": "2026-10-07T08:30:00.000Z", "Source Message Link": link, "Inbox Action": "Route"}
    triage = create_triage(title="Renew vendor insurance", description="Renew the vendor insurance policy.", assignee="Sara Nasser").model_copy(update={"sensitive": True, "sensitivity_reasons": ["contract"]})
    world.triager.script["m-cf2"] = triage
    world.svc.process(make_email("m-cf2", subject="Legal", body="contract termination", day=8))
    world.svc.approve("m-cf2", REVIEWER)
    assert world.tasks.created[-1]["custom"]["Inbox Action"] == "Escalate" and "Source Message Link" not in world.tasks.created[-1]["custom"]  # no link known: not invented


# ------------------------------------------------------------------ reply drafts
def reply_item(world, mid, sender="partner@acme.com"):
    world.triager.script[mid] = Triage(action=Action.REPLY, confidence=0.9, reply=ReplyDraft(body="Yes, we received it."), sensitive=False)
    world.svc.process(make_email(mid, sender=sender, subject="Question", body="Did you receive it?"))
    assert world.store.get(mid)["status"] == "PENDING_REVIEW"  # an external reply always waits for a person


def test_approving_sends_the_very_draft_the_reviewer_saw(world):
    reply_item(world, "d-1")
    assert world.mail.drafts == [{"message_id": "d-1", "body": "Yes, we received it."}]
    world.svc.edit("d-1", REVIEWER, {"reply_body": "Yes, we received it. Thank you."})  # the reviewer's final wording wins
    assert world.mail.sent == [{"message_id": "d-1", "body": "Yes, we received it. Thank you.", "draft_id": "draft-1"}] and world.mail.discarded == []


def test_rejecting_deletes_the_draft_and_sends_nothing(world):
    reply_item(world, "d-2")
    world.svc.reject("d-2", REVIEWER, "not needed")
    assert world.mail.discarded == ["draft-1"] and world.mail.sent == [] and world.store.get("d-2")["status"] == "REJECTED"
    assert any(e["event"] == "draft_discarded" for e in world.store.list_audit("d-2"))


def test_a_draft_that_cannot_be_deleted_does_not_undo_the_rejection(world):
    reply_item(world, "d-3")
    world.mail.fail_next("discard_draft", "graph_503")
    assert world.svc.reject("d-3", REVIEWER)["status"] == "REJECTED" and world.mail.sent == []
    assert any(e["event"] == "draft_discard_failed" for e in world.store.list_audit("d-3"))


def test_a_non_reviewer_cannot_reject_or_discard(world):
    reply_item(world, "d-4")
    with pytest.raises(Forbidden):
        world.svc.reject("d-4", Principal(user_id="x", email="x@x.co", groups=[]))
    assert world.mail.discarded == []


# ------------------------------------------------------------------ Graph draft calls
def test_graph_sends_the_draft_after_setting_the_final_text_and_falls_back_when_it_is_gone():
    g, http, _ = make((200, {}), (202, {}))
    assert g.send_reply("<m@x>", "final text", draft_id="D1") == {"sent": True, "via": "draft"}
    (m1, u1, _, b1), (m2, u2, _, _) = http.calls
    assert (m1, u1.endswith("/me/messages/D1"), b1["body"]["content"]) == ("PATCH", True, "final text") and (m2, u2.endswith("/me/messages/D1/send")) == ("POST", True)
    g, http, _ = make((404, {"error": {"code": "ErrorItemNotFound"}}), (200, {"value": [{"id": "G1", "internetMessageId": "<m@x>"}]}), (202, {}))
    assert g.send_reply("<m@x>", "text", draft_id="D1")["via"] == "reply" and http.calls[-1][1].endswith("/me/messages/G1/reply")


def test_graph_discard_deletes_and_tolerates_an_already_deleted_draft():
    g, http, _ = make((204, {}))
    g.discard_draft("D1"); assert http.calls[0][0] == "DELETE" and http.calls[0][1].endswith("/me/messages/D1")
    g, _, _ = make((404, {}))
    g.discard_draft("D1")
    g, _, _ = make((403, {}))
    with pytest.raises(AdapterError):
        g.discard_draft("D1")


def test_graph_maps_the_web_link():
    from test_graph import MSG
    g, _, _ = make((200, {"value": [{**MSG, "webLink": "https://outlook.office365.com/owa/?ItemID=1"}]}))
    assert g.list_recent_emails(1)[0].web_link == "https://outlook.office365.com/owa/?ItemID=1"


def test_a_plan_limit_on_custom_fields_still_creates_the_task_once_without_them():
    cu, http = adapter((200, FIELDS), (403, {"err": "Custom field usages exceeded for your plan"}), (200, {"id": "x1", "name": "N", "url": "u", "status": {"status": "to do"}}))
    task = cu.create_task({"name": "N", "custom": {"Inbox Action": "Route"}})
    assert task["id"] == "x1" and "exceeded" in task["custom_skipped"]
    posts = [c for c in http.calls if c[0] == "POST"]
    assert len(posts) == 2 and "custom_fields" in posts[0][3] and "custom_fields" not in posts[1][3]  # exactly one retry, without the columns


def test_other_clickup_errors_are_not_retried_and_a_skip_is_reported_to_the_reviewer(world):
    cu, http = adapter((200, FIELDS), (400, {"err": "Name is invalid"}))
    with pytest.raises(AdapterError):
        cu.create_task({"name": "N", "custom": {"Inbox Action": "Route"}})
    assert len([c for c in http.calls if c[0] == "POST"]) == 1  # a real validation error is never repeated
    real_create = world.tasks.create_task
    world.tasks.create_task = lambda f: {**real_create(f), "custom_skipped": "Custom field usages exceeded"}
    world.triager.script["m-skip"] = create_triage(title="Order desks", description="Order six desks.", assignee="Sara Nasser")
    out = world.svc.process(make_email("m-skip", day=6))
    assert out["status"] == "EXECUTED" and "without the list's custom columns" in out["warning"]
    assert any(e["event"] == "custom_fields_skipped" for e in world.store.list_audit("m-skip"))
