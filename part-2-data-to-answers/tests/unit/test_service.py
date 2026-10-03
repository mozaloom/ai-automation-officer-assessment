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

    async def stream_async(self, prompt):
        """Streams the fake answer word by word, running the searches like the real tool would."""
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("secret internal detail")
        text = ""
        for index, filters in enumerate(self.plan):
            yield {"current_tool_use": {"toolUseId": f"t{index}", "name": "query_availability"}}
            self.state[STATE_KEY] = [*self.state[STATE_KEY], query_availability(self.dataset, **filters)]
            yield {"message": {"role": "user", "content": [{"toolResult": {"toolUseId": f"t{index}"}}]}}  # tool finished
        for word in self.reply(prompt).split(" "):
            text += word + " "
            yield {"data": word + " "}
        yield {"result": text.strip()}

    def reply(self, prompt):
        return f"answer to: {prompt}"


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


# ---------------------------------------------------------------------- streaming


async def collect(svc, prompt="Where is tahini in Amman?", sid="s1"):
    return [event async for event in svc.ask_stream(prompt, sid)]


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_stream_emits_start_status_records_deltas_then_done(service):
    events = run(collect(service))
    kinds = [e["type"] for e in events]
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert kinds.index("status") < kinds.index("records") < kinds.index("delta")  # the table can render before the text
    streamed = "".join(e["text"] for e in events if e["type"] == "delta").strip()
    done = events[-1]
    assert streamed == done["answer"] == "answer to: Where is tahini in Amman?"
    assert done["grounded"] is True and done["record_count"] == len(done["records"]) > 0
    assert "replace" not in kinds and "reset" not in kinds
    records = next(e for e in events if e["type"] == "records")
    assert set(records) == {"type", "records", "queries", "record_count", "data_as_of"}


@pytest.mark.parametrize("prompt", [None, "", "   ", "x" * 501])
def test_stream_rejects_bad_prompts_with_one_error_event(service, prompt):
    events = run(collect(service, prompt))
    assert len(events) == 1 and events[0]["type"] == "error" and events[0]["code"] == "invalid_request"


def test_stream_errors_do_not_leak_details(dataset):
    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: FakeAgent(dataset, fail=True))
    events = run(collect(svc))
    assert events[-1]["type"] == "error" and events[-1]["code"] == "agent_error" and "secret" not in str(events)


def test_preamble_before_a_tool_call_is_reset(dataset):
    class Chatty(FakeAgent):
        async def stream_async(self, prompt):
            yield {"data": "Let me check. "}
            async for event in super().stream_async(prompt):
                yield event

    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: Chatty(dataset, plan=[{"product_name": "Tahini"}]))
    kinds = [e["type"] for e in run(collect(svc))]
    assert kinds.index("delta") < kinds.index("reset") < kinds.index("status")


def test_ungrounded_stream_resets_retries_and_recovers(dataset):
    class Liar(FakeAgent):
        def reply(self, prompt):
            return "Sameh Mall Abdoun has 99999 units" if len(self.prompts) == 1 else "Here are the matching records."

    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: Liar(dataset, plan=[{"product_name": "Tahini", "city": "Irbid"}]))
    events = run(collect(svc))
    kinds = [e["type"] for e in events]
    assert "reset" in kinds and events[-1]["type"] == "done" and events[-1]["grounded"] is True
    assert events[-1]["answer"] == "Here are the matching records."
    assert "".join(e["text"] for e in events[kinds.index("reset"):] if e["type"] == "delta").strip() == events[-1]["answer"]


def test_ungrounded_after_retry_falls_back_with_replace(dataset):
    class Stubborn(FakeAgent):
        def reply(self, prompt):
            return "There are 99999 units"

    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: Stubborn(dataset, plan=[{"product_name": "Tahini"}]))
    events = run(collect(svc))
    replace = [e for e in events if e["type"] == "replace"]
    assert replace and replace[0]["text"] == events[-1]["answer"] and events[-1]["grounded"] is False


def test_cancelled_stream_releases_the_session_lock(service):
    import asyncio

    async def scenario():
        stream = service.ask_stream("q", "s")
        await anext(stream)  # start
        await stream.aclose()  # client went away
        return [e async for e in service.ask_stream("again", "s")]

    assert asyncio.run(scenario())[-1]["type"] == "done"
