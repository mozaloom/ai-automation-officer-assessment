import pytest

from helpers import ScriptedTriager
from inbox.adapters.sample import SampleMail, SampleTasks
from inbox.config import Settings
from inbox.service import InboxService
from inbox.store import MemoryStore


@pytest.fixture()
def world():
    """A service wired to in-memory adapters; `world.svc.triager.script` is filled by each test."""
    mail, tasks, store, triager = SampleMail(emails=[]), SampleTasks(), MemoryStore(), ScriptedTriager()
    svc = InboxService(Settings(), store, mail, tasks, triager)
    return type("World", (), {"svc": svc, "mail": mail, "tasks": tasks, "store": store, "triager": triager})()
