"""The 11 scenarios from the brief, against the real service with MOCK adapters (in-memory ClickUp and mailbox, scripted agent).
Real-integration versions live in tests/live and tests/e2e."""

import threading
from datetime import date

import pytest
from pydantic import ValidationError

from conftest import OUTSIDER, REVIEWER, ScriptedTriager, create_triage, make_email
from inbox.adapters.base import AdapterError
from inbox.adapters.sample import SampleTasks
from inbox.models import Action, Principal, ReplyDraft, Status, TaskDraft, Triage
from inbox.service import Conflict, Forbidden, Invalid, InboxService, TriageUnavailable


def run(w, email, triage=None):
    if triage is not None:
        w.triager.script[email.message_id] = triage
    return w.svc.process(email)


def status(w, mid):
    return w.store.get(mid)["status"]


# 1 ------------------------------------------------------------------------------------------ clear request -> task with correct fields
def test_clear_request_creates_a_task_with_the_right_fields(world):
    email = make_email("m-1", body="Prepare the Q4 sales report for Sara by 25 Oct, high priority")
    out = run(world, email, create_triage(title="Prepare the Q4 sales report", description="Prepare the Q4 sales report and send it to Ahmad.", assignee="Sara Nasser", priority="high", due_date=date(2026, 10, 25)))
    assert out["status"] == Status.EXECUTED.value
    (task,) = world.tasks.created
    assert (task["name"], task["assignees"], task["priority"], task["due_date"], task["status"]) == ("Prepare the Q4 sales report", ["Sara Nasser"], "high", "2026-10-25", "to do")
    assert "[email:m-1]" in task["description"] and "Source email from layla@medgan.ai" in task["description"]
    assert world.store.get("m-1")["execution"]["task_id"] == task["id"]
    assert [a["event"] for a in reversed(world.store.list_audit("m-1"))][:3] == ["received", "triaged", "executed"]


# 2 ------------------------------------------------------------------------------------------ informational -> IGNORE
def test_informational_email_is_ignored(world):
    out = run(world, make_email("m-2", body="Thanks for sending the report."), Triage(action=Action.IGNORE, confidence=0.95, rationale="thanks only"))
    assert out["status"] == Status.IGNORED.value and world.tasks.created == [] and world.mail.sent == []


# 3 ------------------------------------------------------------------------------------------ ambiguous -> HUMAN_REVIEW
def test_ambiguous_request_goes_to_review(world):
    run(world, make_email("m-3", body="Can someone take care of the client issue?"), Triage(action=Action.HUMAN_REVIEW, confidence=0.4, rationale="no owner, no scope", missing_fields=["assignee", "scope"]))
    assert status(world, "m-3") == Status.PENDING_REVIEW.value and world.tasks.created == []
    assert "missing: assignee, scope" in world.store.get("m-3")["proposal"]["reasons"][0]


def test_a_confident_but_incomplete_create_is_still_reviewed(world):
    run(world, make_email("m-3b"), create_triage(title="Look into the client issue"))  # no assignee, no description
    assert status(world, "m-3b") == Status.PENDING_REVIEW.value and world.tasks.created == []


# 4 ------------------------------------------------------------------------------------------ existing work -> find and update the task
def test_update_finds_and_updates_the_matching_task(world):
    out = run(world, make_email("m-4", sender="sara@medgan.ai", body="The Q3 marketing report moved to 27 Oct and is blocked"),
              Triage(action=Action.UPDATE_TASK, confidence=0.9, target_task_id="t1", task=TaskDraft(title="Q3 marketing report", status="blocked", due_date=date(2026, 10, 27))))
    assert out["status"] == Status.EXECUTED.value and world.tasks.created == []
    t1 = world.tasks.tasks["t1"]
    assert (t1["status"], t1["due_date"]) == ("blocked", "2026-10-27")
    assert sorted(world.tasks.updated[0]) == ["due_date", "id", "status"]


def test_update_with_a_weak_match_or_missing_target_is_reviewed(world):
    run(world, make_email("m-4b"), Triage(action=Action.UPDATE_TASK, confidence=0.9, target_task_id="t2", task=TaskDraft(title="Q3 marketing report", status="done")))
    run(world, make_email("m-4c"), Triage(action=Action.UPDATE_TASK, confidence=0.9, target_task_id="nope", task=TaskDraft(title="Q3 marketing report", status="done")))
    assert status(world, "m-4b") == status(world, "m-4c") == Status.PENDING_REVIEW.value and world.tasks.updated == []


def test_changing_the_assignee_of_a_task_needs_approval(world):
    run(world, make_email("m-4d"), Triage(action=Action.UPDATE_TASK, confidence=0.9, target_task_id="t1", task=TaskDraft(title="Q3 marketing report", assignee="Ahmad Haddad")))
    assert status(world, "m-4d") == Status.PENDING_REVIEW.value and world.tasks.updated == []


# 5 ------------------------------------------------------------------------------------------ repeated delivery -> no duplicate
def test_repeated_delivery_creates_one_task(world):
    email = make_email("m-5")
    first = run(world, email, create_triage(title="Prepare the budget deck", description="Budget deck for Q4", assignee="Ahmad Haddad"))
    second = world.svc.process(email)
    assert first["outcome"] == "processed" and second["outcome"] == "duplicate"
    assert len(world.tasks.created) == 1 and world.triager.calls == 1
    assert any(a["event"] == "duplicate_delivery" for a in world.store.list_audit("m-5"))


def test_concurrent_delivery_creates_one_task(world):
    email = make_email("m-5c")
    world.triager.script["m-5c"] = create_triage(title="Prepare the budget deck", description="Budget deck", assignee="Ahmad Haddad")
    results = []
    threads = [threading.Thread(target=lambda: results.append(world.svc.process(email))) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(world.tasks.created) == 1 and world.triager.calls == 1
    assert sorted(r["outcome"] for r in results).count("processed") == 1


# 6 ------------------------------------------------------------------------------------------ different emails about existing work -> duplicate check
def test_a_different_email_about_existing_work_is_flagged_as_duplicate(world):
    run(world, make_email("m-6a"), create_triage(title="Website homepage banner redesign", description="Track it", assignee="Mohammed Zaloom"))
    assert status(world, "m-6a") == Status.PENDING_REVIEW.value and world.tasks.created == []
    assert any("likely duplicate" in r for r in world.store.get("m-6a")["proposal"]["reasons"])
    assert world.store.get("m-6a")["proposal"]["matches"][0]["task_id"] == "t2"


def test_a_partial_title_overlap_is_a_possible_duplicate_for_a_person(world):
    run(world, make_email("m-6b"), create_triage(title="Redesign homepage layout", description="Layout work", assignee="Sara Nasser"))
    assert status(world, "m-6b") == Status.PENDING_REVIEW.value
    assert any("possible duplicate" in r for r in world.store.get("m-6b")["proposal"]["reasons"])


# 7 ------------------------------------------------------------------------------------------ sensitive external reply -> approval first
def test_sensitive_external_reply_is_sent_only_after_approval(world):
    email = make_email("m-7", sender="partner@acme-supplies.com", subject="Contract question", body="Please confirm the contract termination date and send the legal agreement")
    run(world, email, Triage(action=Action.REPLY, confidence=0.9, reply=ReplyDraft(body="We will confirm the termination date shortly."), sensitive=True, sensitivity_reasons=["contract termination"]))
    assert status(world, "m-7") == Status.PENDING_REVIEW.value and world.mail.sent == []
    assert world.store.get("m-7")["draft"]["draft_id"] == "draft-1"  # a draft exists, nothing was sent
    with pytest.raises(Forbidden):
        world.svc.approve("m-7", OUTSIDER)
    assert world.mail.sent == [] and status(world, "m-7") == Status.PENDING_REVIEW.value
    world.svc.approve("m-7", REVIEWER)
    assert len(world.mail.sent) == 1 and status(world, "m-7") == Status.EXECUTED.value
    with pytest.raises(Conflict):
        world.svc.approve("m-7", REVIEWER)
    assert len(world.mail.sent) == 1


def test_every_reply_needs_approval_by_default_even_a_harmless_internal_one(world):
    run(world, make_email("m-7b", sender="khaled@medgan.ai"), Triage(action=Action.REPLY, confidence=0.95, reply=ReplyDraft(body="Yes, it was sent yesterday.")))
    assert status(world, "m-7b") == Status.PENDING_REVIEW.value and world.mail.sent == []


def test_auto_send_can_be_enabled_by_policy_but_not_for_external_or_sensitive(world):
    from dataclasses import replace
    world.svc.settings = replace(world.svc.settings, policy=replace(world.svc.settings.policy, auto_send_replies=True))
    run(world, make_email("m-7c", sender="khaled@medgan.ai"), Triage(action=Action.REPLY, confidence=0.95, reply=ReplyDraft(body="Yes, it was sent.")))
    run(world, make_email("m-7d", sender="client@outside.com"), Triage(action=Action.REPLY, confidence=0.95, reply=ReplyDraft(body="Sure.")))
    assert status(world, "m-7c") == Status.EXECUTED.value and status(world, "m-7d") == Status.PENDING_REVIEW.value and len(world.mail.sent) == 1


def test_sensitive_keywords_force_review_even_if_the_agent_did_not_flag_it(world):
    run(world, make_email("m-7e", body="Please update the salary spreadsheet task"), create_triage(title="Update the salary spreadsheet", description="Update it", assignee="Sara Nasser"))
    assert status(world, "m-7e") == Status.PENDING_REVIEW.value and world.tasks.created == []


# 8 ------------------------------------------------------------------------------------------ missing fields -> nothing invented
def test_missing_fields_are_not_invented_and_block_approval_until_edited(world):
    run(world, make_email("m-8"), create_triage(title="October newsletter"))
    resolved = world.store.get("m-8")["proposal"]["resolved"]
    assert resolved["assignee_id"] is None and resolved["due_date"] is None and resolved["priority_source"] == "configured_default"
    with pytest.raises(Invalid) as err:
        world.svc.approve("m-8", REVIEWER)
    assert "missing assignee" in err.value.problems and world.tasks.created == []
    with pytest.raises(Invalid):
        world.svc.edit("m-8", REVIEWER, {"task": {"assignee": "Nobody Here"}})  # an unknown person is not accepted either
    out = world.svc.edit("m-8", REVIEWER, {"task": {"assignee": "Ahmad Haddad"}})
    assert out["status"] == Status.EXECUTED.value and world.tasks.created[0]["assignees"] == ["Ahmad Haddad"] and world.tasks.created[0]["due_date"] is None
    assert world.store.get("m-8")["original_proposal"]["resolved"]["assignee_id"] is None  # the original is kept


def test_an_invalid_due_date_or_status_is_dropped_and_flagged_never_guessed(world):
    run(world, make_email("m-8b", day=5), create_triage(title="Plan the offsite", description="Plan it", assignee="Sara Nasser", due_date=date(2020, 1, 1), status="someday"))
    problems = world.store.get("m-8b")["proposal"]["resolved"]["problems"]
    assert any("before the email was received" in p for p in problems) and any("not a status" in p for p in problems)
    assert status(world, "m-8b") == Status.PENDING_REVIEW.value and world.tasks.created == []


def test_ambiguous_assignee_is_not_guessed(world):
    world.tasks.members.append(type(world.tasks.members[0])(id="104", username="Sara Khoury", email="sara.k@medgan.ai"))
    run(world, make_email("m-8c"), create_triage(title="Prepare slides", description="Slides", assignee="Sara"))
    assert world.store.get("m-8c")["proposal"]["resolved"]["assignee_id"] is None and status(world, "m-8c") == Status.PENDING_REVIEW.value


# 9 ------------------------------------------------------------------------------------------ API failures -> safe, recoverable
def test_clickup_failure_during_create_is_recoverable_without_duplicates(world):
    world.tasks.fail_next("create_task", "timeout", retryable=True)
    out = run(world, make_email("m-9"), create_triage(title="Prepare the audit pack", description="Audit pack", assignee="Sara Nasser"))
    assert out["status"] == Status.FAILED.value and world.store.get("m-9")["error"]["retryable"] and world.tasks.created == []
    world.svc.retry("m-9", REVIEWER)
    assert status(world, "m-9") == Status.EXECUTED.value and len(world.tasks.created) == 1


def test_a_lost_answer_after_a_successful_create_does_not_duplicate_on_retry(world):
    original = world.tasks.create_task

    def create_then_lose_the_answer(fields):
        original(fields)
        raise AdapterError("timeout", "no answer", retryable=True)

    world.tasks.create_task = create_then_lose_the_answer
    run(world, make_email("m-9b"), create_triage(title="Prepare the audit pack", description="Audit pack", assignee="Sara Nasser"))
    assert status(world, "m-9b") == Status.FAILED.value and len(world.tasks.created) == 1  # it did get created
    world.tasks.create_task = original
    world.svc.retry("m-9b", REVIEWER)
    assert status(world, "m-9b") == Status.EXECUTED.value and len(world.tasks.created) == 1  # adopted, not created again
    assert world.store.get("m-9b")["execution"]["adopted"] is True


def test_agent_unavailable_fails_safely_and_can_be_retried(world):
    world.triager.error = TriageUnavailable("model throttled")
    out = run(world, make_email("m-9c"))
    assert out["status"] == Status.FAILED.value and world.store.get("m-9c")["error"]["stage"] == "triage" and world.tasks.created == []
    world.triager.error = None
    world.mail.add(make_email("m-9c"))
    world.triager.script["m-9c"] = Triage(action=Action.IGNORE, confidence=0.9)
    world.svc.retry("m-9c", REVIEWER)
    assert status(world, "m-9c") == Status.IGNORED.value


def test_mailbox_failure_during_sync_is_reported_and_leaves_no_partial_state(world):
    world.mail.fail_next("list_recent_emails", "graph_503", retryable=True)
    with pytest.raises(AdapterError):
        world.svc.sync(REVIEWER)
    assert world.store.list_messages() == [] and world.store.list_audit()[0]["event"] == "sync_failed"


def test_a_rejected_request_failure_is_not_retryable(world):
    world.tasks.fail_next("create_task", "clickup_400", retryable=False)
    run(world, make_email("m-9d"), create_triage(title="Prepare the audit pack", description="Audit pack", assignee="Sara Nasser"))
    assert status(world, "m-9d") == Status.FAILED.value
    with pytest.raises(Conflict):
        world.svc.retry("m-9d", REVIEWER)


def test_invalid_agent_output_becomes_a_review_item_not_an_action(world):
    try:
        Triage.model_validate({"action": "CREATE_TASK", "confidence": 0.9})
    except ValidationError as err:
        world.triager.error = err
    out = run(world, make_email("m-9e"))
    assert out["status"] == Status.PENDING_REVIEW.value and world.tasks.created == []


def test_low_confidence_is_reviewed(world):
    run(world, make_email("m-9f"), Triage(action=Action.CREATE_TASK, confidence=0.4, task=TaskDraft(title="Maybe a task", description="x", assignee="Sara Nasser")))
    assert status(world, "m-9f") == Status.PENDING_REVIEW.value


# 10 ------------------------------------------------------------------------------------------ unauthorized -> rejected
@pytest.mark.parametrize("who", [OUTSIDER, None, Principal(user_id="", groups=["inbox-reviewers"])])
def test_unauthorized_callers_cannot_do_anything(world, who):
    run(world, make_email("m-10"), Triage(action=Action.HUMAN_REVIEW, confidence=0.3))
    for call in (lambda: world.svc.approve("m-10", who), lambda: world.svc.reject("m-10", who), lambda: world.svc.edit("m-10", who, {}), lambda: world.svc.retry("m-10", who), lambda: world.svc.sync(who)):
        with pytest.raises(Forbidden):
            call()
    assert status(world, "m-10") == Status.PENDING_REVIEW.value and world.tasks.created == [] and world.mail.sent == []


def test_denied_attempts_are_audited(world):
    run(world, make_email("m-10b"), Triage(action=Action.HUMAN_REVIEW, confidence=0.3))
    with pytest.raises(Forbidden):
        world.svc.reject("m-10b", OUTSIDER)
    assert any(a["event"] == "unauthorized" and a["actor"] == "outsider@medgan.ai" for a in world.store.list_audit())


# 11 ------------------------------------------------------------------------------------------ rejection -> nothing external
def test_rejection_executes_nothing(world):
    run(world, make_email("m-11"), create_triage(title="Redesign homepage layout", description="Layout", assignee="Sara Nasser"))
    assert status(world, "m-11") == Status.PENDING_REVIEW.value
    world.svc.reject("m-11", REVIEWER, "not needed")
    assert status(world, "m-11") == Status.REJECTED.value and world.tasks.created == [] and world.tasks.updated == [] and world.mail.sent == []
    with pytest.raises(Conflict):
        world.svc.approve("m-11", REVIEWER)
    with pytest.raises(Conflict):
        world.svc.reject("m-11", REVIEWER)
    assert world.tasks.created == []


# approval is a one-shot gate ------------------------------------------------------------------
def test_concurrent_approvals_execute_exactly_once(world):
    run(world, make_email("m-12"), create_triage(title="Redesign homepage layout", description="Layout", assignee="Sara Nasser"))
    outcomes = []

    def approve():
        try:
            world.svc.approve("m-12", REVIEWER)
            outcomes.append("ok")
        except Conflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=approve) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert outcomes.count("ok") == 1 and len(world.tasks.created) == 1


def test_an_abandoned_processing_lease_can_be_taken_over(world):
    from datetime import datetime, timedelta, timezone
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    world.svc.clock = lambda: now
    email = make_email("m-13")
    world.triager.script["m-13"] = Triage(action=Action.IGNORE, confidence=0.9)
    world.store.claim("m-13", {"status": "PROCESSING", "lease_until": (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "received_at": "2026-10-05T08:30:00.000Z", "attempts": 1})
    out = world.svc.process(email)
    assert out["status"] == Status.IGNORED.value
    # a live lease is respected
    world.store.claim("m-14", {"status": "PROCESSING", "lease_until": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z"), "received_at": "2026-10-05T08:30:00.000Z", "attempts": 1})
    assert world.svc.process(make_email("m-14"))["outcome"] == "duplicate"


def test_sync_processes_the_mailbox_once(world):
    for i in range(3):
        world.mail.add(make_email(f"s-{i}", day=5 + i))
    first, second = world.svc.sync(REVIEWER), world.svc.sync(REVIEWER)
    assert (first["new"], first["duplicates"]) == (3, 0) and (second["new"], second["duplicates"]) == (0, 3) and world.triager.calls == 3


def test_stored_email_content_is_minimal(world):
    run(world, make_email("m-15", body="x" * 5000), Triage(action=Action.IGNORE, confidence=0.9))
    item = world.store.get("m-15")
    assert len(item["body_excerpt"]) == 1500 and "body" not in item
    assert all("x" * 20 not in str(a) for a in world.store.list_audit("m-15"))  # audit never holds email text
