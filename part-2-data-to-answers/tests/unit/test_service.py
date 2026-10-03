"""AvailabilityService with a fake agent: routing, validation, session cache, response shape."""

import threading

import pytest

from agent.service import AvailabilityService
from config import Settings
from tools.availability import DataStore, local_loader, query_availability
from tools.strands_tool import STATE_KEY


class FakeState(dict):
    def set(self, key, value):
        self[key] = value


class FakeAgent:
    """Mimics the Strands agent: runs real searches, stores them in state like the tool does."""

    def __init__(self, dataset, plan=None, fail=False):
        self.state, self.dataset, self.plan, self.fail, self.prompts = FakeState({STATE_KEY: []}), dataset, plan or [{}], fail, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("secret internal detail")
        for filters in self.plan:
            self.state[STATE_KEY] = [*self.state[STATE_KEY], query_availability(self.dataset, **filters)]
        return f"answer to: {prompt}"

    def get(self, key, default=None):
        return self.state.get(key, default)


@pytest.fixture()
def service(dataset):
    settings = Settings(session_cache_size=2)
    store = DataStore(local_loader(settings.data_path))
    agents = []

    def factory():
        agent = FakeAgent(dataset, plan=[{"product_name": "Tahini", "city": "Amman"}])
        agents.append(agent)
        return agent

    svc = AvailabilityService(settings, store, factory)
    svc.agents = agents
    return svc


def test_ask_returns_answer_records_and_provenance(service, raw_rows):
    out = service.handle({"action": "ask", "prompt": "Where is tahini in Amman?"}, "s1")
    assert out["answer"].startswith("answer to:")
    assert out["record_count"] == len(out["records"]) > 0
    assert out["queries"][0]["filters"] == {"product_name": "Tahini", "city": "Amman"}
    newest = max(__import__("datetime").datetime.strptime(r["last_updated"], "%d/%m/%Y").date()
                 for r in raw_rows if r["product_name"] == "Tahini" and r["city"] == "Amman")
    assert out["data_as_of"] == newest.isoformat() and out["session_id"] == "s1"


def test_default_action_is_ask_and_payload_session_is_used(service):
    out = service.handle({"prompt": "hi"}, None)
    assert out["session_id"] == "anonymous"
    assert service.handle({"prompt": "hi", "session_id": "from-payload"})["session_id"] == "from-payload"


@pytest.mark.parametrize("payload", [None, [], "text", 7])
def test_non_object_payloads_are_rejected(service, payload):
    assert service.handle(payload)["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("prompt", [None, "", "   ", 5, ["x"]])
def test_bad_prompts_are_rejected(service, prompt):
    assert service.handle({"action": "ask", "prompt": prompt})["error"]["code"] == "invalid_request"


def test_overlong_prompt_is_rejected(service):
    out = service.handle({"action": "ask", "prompt": "x" * 501})
    assert out["error"]["code"] == "invalid_request" and "500" in out["error"]["message"]


def test_unknown_action_is_rejected(service):
    assert "drop_tables" in service.handle({"action": "drop_tables"})["error"]["message"]


def test_dashboard_action_uses_filters(service):
    out = service.handle({"action": "dashboard", "filters": {"city": "Irbid"}})
    assert out["filters"] == {"city": "Irbid"} and out["kpis"]["listings"] == 114
    assert service.handle({"action": "dashboard", "filters": "bad"})["error"]["code"] == "invalid_request"


def test_same_session_reuses_agent_and_cache_is_bounded(service):
    for sid in ("a", "a", "b", "c"):
        service.handle({"prompt": "q"}, sid)
    assert len(service.agents) == 3  # a, b, c created once each
    assert len(service._sessions) == 2 and "a" not in service._sessions  # LRU evicted


def test_tool_state_is_cleared_between_turns(service):
    service.handle({"prompt": "one"}, "s")
    second = service.handle({"prompt": "two"}, "s")
    assert len(second["queries"]) == 1


def test_agent_errors_do_not_leak_details(dataset):
    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: FakeAgent(dataset, fail=True))
    out = svc.handle({"prompt": "boom"}, "s")
    assert out["error"]["code"] == "agent_error" and "secret" not in str(out)


def test_records_are_unioned_across_tool_calls(dataset):
    agent = FakeAgent(dataset, plan=[{"product_name": "Tahini", "city": "Amman"}, {"product_name": "Tahini", "city": "Irbid"}])
    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: agent)
    out = svc.handle({"prompt": "compare"}, "s")
    assert {r["city"] for r in out["records"]} == {"Amman", "Irbid"}
    assert len(out["queries"]) == 2


def test_ambiguity_and_no_match_are_surfaced(dataset):
    agent = FakeAgent(dataset, plan=[{"product_name": "tea"}])
    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: agent)
    out = svc.handle({"prompt": "tea?"}, "s")
    assert out["records"] == [] and out["queries"][0]["ambiguous"]["candidates"]


def test_same_session_requests_are_serialised(dataset):
    running, overlap = [0], [False]

    class Slow(FakeAgent):
        def __call__(self, prompt):
            running[0] += 1
            overlap[0] |= running[0] > 1
            threading.Event().wait(0.05)
            running[0] -= 1
            return super().__call__(prompt)

    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: Slow(dataset))
    threads = [threading.Thread(target=svc.handle, args=({"prompt": "q"}, "same")) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert overlap[0] is False
