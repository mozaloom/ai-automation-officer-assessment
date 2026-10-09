"""ClickUp adapter (fake HTTP), resolution rules and the policy, tested directly."""

from datetime import date

import pytest

from conftest import make_email
from inbox.adapters.base import AdapterError
from inbox.adapters.clickup import ClickUpAdapter
from inbox.config import PolicyConfig
from inbox.models import Action, Member, Triage, TaskDraft
from inbox.policy import decide, is_external, sensitive_hits
from inbox.resolve import find_matches, resolve_assignee, resolve_priority, resolve_status, similarity, validate_due_date

MEMBERS = [Member(id="1", username="Mohammed Zaloom", email="mohammed@medgan.ai"), Member(id="2", username="Sara Nasser", email="sara@medgan.ai"), Member(id="3", username="Sara Khoury", email="sk@medgan.ai")]


class FakeHttp:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def adapter(*responses):
    http = FakeHttp(*responses)
    return ClickUpAdapter("pk_test", "L1", "T1", http=http, sleep=lambda s: None), http


# ------------------------------------------------------------------ ClickUp adapter
def test_create_task_sends_the_mapped_fields_and_the_token_header():
    cu, http = adapter((200, {"id": "x1", "name": "N", "url": "https://u", "status": {"status": "to do"}, "assignees": [{"id": 7, "username": "A"}]}))
    task = cu.create_task({"name": "N", "description": "D", "assignee_id": "7", "priority": 2, "due_date": date(2026, 10, 25), "status": "to do"})
    method, url, headers, body = http.calls[0]
    assert (method, url.endswith("/list/L1/task"), headers["Authorization"]) == ("POST", True, "pk_test")
    assert body == {"name": "N", "description": "D", "priority": 2, "status": "to do", "due_date": 1792929600000, "due_date_time": False, "assignees": [7]}
    assert task["id"] == "x1" and task["assignees"] == ["A"]


def test_reads_are_retried_but_a_create_is_never_retried():
    cu, http = adapter((503, {}), (200, {"statuses": [{"status": "to do"}]}))
    assert cu.list_statuses() == ["to do"] and len(http.calls) == 2
    cu, http = adapter(AdapterError("timeout", "slow", retryable=True), (200, {"id": "x"}))
    with pytest.raises(AdapterError) as err:
        cu.create_task({"name": "N"})
    assert err.value.retryable and len(http.calls) == 1  # a repeated POST could duplicate the task


def test_errors_are_classified():
    for status, retryable in ((400, False), (401, False), (404, False), (429, True), (500, True)):
        cu, _ = adapter(*[(status, {"err": "nope"})] * 3)
        with pytest.raises(AdapterError) as err:
            cu.get_task("x")
        assert (err.value.code, err.value.retryable) == (f"clickup_{status}", retryable)


def test_members_require_the_configured_workspace_and_task_listing_pages():
    cu, _ = adapter((200, {"teams": [{"id": "OTHER", "members": []}]}))
    with pytest.raises(AdapterError):
        cu.list_members()
    page = [{"id": str(i), "name": f"t{i}", "status": {"status": "to do"}} for i in range(100)]
    cu, http = adapter((200, {"tasks": page}), (200, {"tasks": page[:3]}))
    assert len(cu.list_tasks()) == 103 and len(http.calls) == 2


def test_the_token_is_never_part_of_an_error_message():
    cu, _ = adapter((401, {"err": "Token invalid"}))
    with pytest.raises(AdapterError) as err:
        cu.get_task("x")
    assert "pk_test" not in str(err.value)


# ------------------------------------------------------------------ resolution
def test_assignee_resolution_is_exact_or_unambiguous():
    assert resolve_assignee("sara@medgan.ai", MEMBERS)[0].id == "2"
    assert resolve_assignee("Mohammed Zaloom", MEMBERS)[0].id == "1"
    assert resolve_assignee("mohammed", MEMBERS)[0].id == "1"
    assert resolve_assignee("Sara", MEMBERS)[0] is None and "several" in resolve_assignee("Sara", MEMBERS)[1]
    assert resolve_assignee("Nobody", MEMBERS)[0] is None and resolve_assignee("", MEMBERS)[1] == "assignee missing"


def test_priority_status_and_due_date_rules():
    cfg = PolicyConfig()
    assert resolve_priority("urgent", cfg) == (1, "email") and resolve_priority(None, cfg) == (3, "configured_default")
    assert resolve_priority(None, PolicyConfig(default_priority=None)) == (None, "none")
    assert resolve_status("TO DO", ["to do"]) == ("to do", None) and resolve_status("later", ["to do"])[0] is None and resolve_status(None, [])[1] is None
    received = date(2026, 10, 5)
    assert validate_due_date(date(2026, 10, 25), received, cfg) == (date(2026, 10, 25), None)
    assert validate_due_date(date(2026, 10, 1), received, cfg)[0] is None and validate_due_date(date(2030, 1, 1), received, cfg)[0] is None


def test_similarity_and_matching():
    assert similarity("Prepare the Q3 marketing report", "Q3 marketing report") >= 0.8
    assert similarity("Order pizza", "Q3 marketing report") == 0.0 and similarity("", "x") == 0.0
    tasks = [{"id": "1", "name": "Website banner", "description": "x [email:m-9]", "url": "u", "status": "to do"}, {"id": "2", "name": "Something else", "description": ""}]
    matches = find_matches("Totally different", "m-9", tasks)
    assert [m.task_id for m in matches] == ["1"] and matches[0].exact_marker and matches[0].score == 1.0


# ------------------------------------------------------------------ policy
def test_policy_basics():
    cfg = PolicyConfig()
    assert is_external("x@gmail.com", cfg) and not is_external("x@medgan.ai", cfg)
    assert sensitive_hits(make_email(body="Please process the Payroll run"), cfg) == ["payroll"]
    assert sensitive_hits(make_email(body="a perfectly normal request"), cfg) == []
    ignore = decide(Triage(action=Action.IGNORE, confidence=0.9), make_email(), None, [], cfg)
    assert (ignore.route, ignore.action) == ("auto", Action.IGNORE)
    review = decide(Triage(action=Action.HUMAN_REVIEW, confidence=0.1, rationale="unclear"), make_email(), None, [], cfg)
    assert review.route == "review" and review.reasons == ["unclear"]


def test_triage_schema_rejects_inconsistent_output():
    for bad in ({"action": "CREATE_TASK", "confidence": 0.9}, {"action": "UPDATE_TASK", "confidence": 0.9, "task": {"title": "x"}}, {"action": "REPLY", "confidence": 0.9}, {"action": "DELETE_EVERYTHING", "confidence": 1}, {"action": "IGNORE", "confidence": 3}):
        with pytest.raises(Exception):
            Triage.model_validate(bad)
    ok = Triage.model_validate({"action": "CREATE_TASK", "confidence": 0.8, "task": {"title": "  Hello  ", "assignee": "  ", "priority": "high", "due_date": "2026-10-25"}})
    assert ok.task.title == "Hello" and ok.task.assignee is None and ok.task.due_date == date(2026, 10, 25)
    with pytest.raises(Exception):
        TaskDraft(priority="whenever")


def test_the_external_check_uses_the_real_recipient_not_the_agents_claim():
    from dataclasses import replace
    from inbox.models import ReplyDraft
    cfg = replace(PolicyConfig(), auto_send_replies=True)
    lie = Triage(action=Action.REPLY, confidence=0.99, reply=ReplyDraft(body="Sure", to=["colleague@medgan.ai"]))  # claims an internal recipient
    external_sender = make_email(sender="stranger@outside.com")
    assert decide(lie, external_sender, None, [], cfg).route == "review"
    assert decide(lie, make_email(sender="khaled@medgan.ai"), None, [], cfg).route == "auto"
    spoof = make_email(sender="x@medgan.ai.evil.com")
    assert is_external(spoof.sender, cfg) and decide(lie, spoof, None, [], cfg).route == "review"
