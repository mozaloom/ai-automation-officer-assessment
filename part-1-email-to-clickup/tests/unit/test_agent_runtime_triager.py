"""AgentRuntimeTriager with a fake bedrock-agentcore client: validation, bounded retries of transient errors only."""

import io
import json

import pytest
from botocore.exceptions import ClientError

from helpers import make_email
from inbox.agent import AgentRuntimeTriager
from inbox.config import Settings
from inbox.models import Action
from inbox.service import TriageUnavailable

GOOD = {"action": "CREATE_TASK", "confidence": 0.9, "task": {"title": "Do it", "assignee": "Sara"}}


def err(code):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "InvokeAgentRuntime")


class Client:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def invoke_agent_runtime(self, **kw):
        self.calls.append(kw)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return {"response": io.BytesIO(json.dumps(out).encode() if not isinstance(out, bytes) else out)}


def triager(*outcomes):
    client = Client(*outcomes)
    return AgentRuntimeTriager(Settings(agent_runtime_arn="arn:x"), client=client, sleep=lambda s: None), client


def test_valid_answer_is_validated_and_each_call_gets_a_fresh_session():
    t, c = triager(GOOD, GOOD)
    assert t.triage(make_email(), {}).action == Action.CREATE_TASK
    t.triage(make_email(), {})
    assert c.calls[0]["runtimeSessionId"] != c.calls[1]["runtimeSessionId"] and c.calls[0]["agentRuntimeArn"] == "arn:x"
    assert json.loads(c.calls[0]["payload"])["email"]["message_id"] == "m-1"


def test_transient_runtime_errors_are_retried_a_bounded_number_of_times():
    t, c = triager(err("RuntimeClientError"), err("ThrottlingException"), GOOD)
    assert t.triage(make_email(), {}).action == Action.CREATE_TASK and len(c.calls) == 3
    t, c = triager(*[err("RuntimeClientError")] * 5)
    with pytest.raises(TriageUnavailable):
        t.triage(make_email(), {})
    assert len(c.calls) == 3  # bounded


def test_permanent_errors_are_not_retried():
    for code in ("AccessDeniedException", "ValidationException", "ResourceNotFoundException"):
        t, c = triager(err(code), GOOD)
        with pytest.raises(TriageUnavailable) as e:
            t.triage(make_email(), {})
        assert len(c.calls) == 1 and code in str(e.value)


def test_garbage_or_refusals_become_value_errors_so_a_person_decides():
    for bad in (b"not json", {"error": {"code": "invalid_request"}}, {"action": "DELETE_ALL", "confidence": 1}, [1, 2]):
        t, _ = triager(bad)
        with pytest.raises(ValueError):
            t.triage(make_email(), {})
