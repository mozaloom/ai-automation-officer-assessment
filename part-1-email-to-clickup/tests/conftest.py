from datetime import datetime, timezone

import pytest

from inbox.adapters.sample import SampleMail, SampleTasks
from inbox.config import Settings
from inbox.models import Action, Email, Principal, ReplyDraft, TaskDraft, Triage
from inbox.service import InboxService
from inbox.store import MemoryStore

REVIEWER = Principal(user_id="u-1", email="reviewer@medgan.ai", groups=["inbox-reviewers"])
OUTSIDER = Principal(user_id="u-2", email="outsider@medgan.ai", groups=[])


class ScriptedTriager:
    """Stands in for the agent: returns the Triage scripted for a message id. Counts calls."""

    def __init__(self, script: dict | None = None, default: Triage | None = None):
        self.script, self.default, self.calls = script or {}, default, 0
        self.error: Exception | None = None

    def triage(self, email: Email, context: dict) -> Triage:
        self.calls += 1
        if self.error:
            raise self.error
        return self.script.get(email.message_id) or self.default or Triage(action=Action.IGNORE, confidence=0.9)


def make_email(message_id="m-1", sender="layla@medgan.ai", subject="Hello", body="Hi", day=5) -> Email:
    return Email(message_id=message_id, sender=sender, subject=subject, body=body, received_at=datetime(2026, 10, day, 8, 30, tzinfo=timezone.utc), to=["xpand@medgan.ai"])


def create_triage(**task) -> Triage:
    return Triage(action=Action.CREATE_TASK, confidence=0.92, rationale="clear request", task=TaskDraft(**task))


@pytest.fixture()
def world():
    """A service wired to in-memory adapters; `world.svc.triager.script` is filled by each test."""
    mail, tasks, store, triager = SampleMail(emails=[]), SampleTasks(), MemoryStore(), ScriptedTriager()
    svc = InboxService(Settings(), store, mail, tasks, triager)
    return type("World", (), {"svc": svc, "mail": mail, "tasks": tasks, "store": store, "triager": triager})()
