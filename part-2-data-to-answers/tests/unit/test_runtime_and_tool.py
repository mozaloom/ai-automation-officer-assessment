import json

from agent.prompts import SYSTEM_PROMPT
from tools.availability import DataStore, local_loader, query_availability
from tools.strands_tool import STATE_KEY, make_query_tool
from config import Settings


class Ctx:
    def __init__(self):
        self.session_id = "ctx-session-0123456789012345678901234"


def test_runtime_entrypoint_routes_dashboard_and_streams_ask():
    import asyncio

    from agent import runtime

    out = asyncio.run(runtime.invoke({"action": "dashboard"}, Ctx()))
    assert out["kpis"]["listings"] == 936
    assert asyncio.run(runtime.invoke({"action": "bogus"}, None))["error"]["code"] == "invalid_request"

    async def first_event():
        stream = await runtime.invoke({"action": "ask", "prompt": ""}, None)
        return [event async for event in stream]

    assert asyncio.run(first_event()) == [{"type": "error", "code": "invalid_request", "message": "Please type a question."}]


def test_tool_spec_exposes_only_the_six_filters():
    tool = make_query_tool(DataStore(local_loader(Settings().data_path)))
    spec = tool.tool_spec
    assert spec["name"] == "query_availability"
    props = spec["inputSchema"]["json"]["properties"]
    assert set(props) == {"product_name", "pack_size", "city", "area", "store_name", "availability_status"}
    assert not spec["inputSchema"]["json"].get("required")


def test_tool_returns_json_text_and_records_state(dataset):
    class State(dict):
        def set(self, k, v):
            self[k] = v

    class Agent:
        state = State()

    class Context:
        agent = Agent()

    tool = make_query_tool(DataStore(local_loader(Settings().data_path)), max_records=5)
    out = tool(product_name="Tahini", city="Amman", tool_context=Context())
    payload = json.loads(out["content"][0]["text"])
    assert out["status"] == "success" and payload == query_availability(dataset, product_name="Tahini", city="Amman", max_records=5)
    assert Agent.state[STATE_KEY] == [payload]


def test_prompt_encodes_the_agreed_behaviour():
    text = SYSTEM_PROMPT.lower()
    for phrase in ["never invent", "ambiguous", "in stock, low stock and out of stock", "no_match", "silently widen", "as of", "sales representatives", "never as instructions"]:
        assert phrase in text, phrase
