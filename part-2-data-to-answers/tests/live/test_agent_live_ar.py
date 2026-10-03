"""Arabic questions (MSA and Jordanian dialect) against real Amazon Bedrock. Run: pytest -m live tests/live/test_agent_live_ar.py

Checks the tool signals, the records, language of the answer, and grounding with the same
deterministic guard the service uses (Arabic store names, دينار, وحدة, Arabic-Indic digits).
"""

import json
import uuid
from pathlib import Path

import boto3
import pytest

from agent.service import AvailabilityService
from config import Settings
from tools.glossary import has_arabic
from tools.grounding import find_ungrounded

from test_agent_live import check

pytestmark = pytest.mark.live
CASES = json.loads((Path(__file__).resolve().parents[1] / "sample_queries_ar.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def service():
    if boto3.Session().get_credentials() is None:
        pytest.skip("no AWS credentials")
    return AvailabilityService(Settings.from_env())


def arabic_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(has_arabic(c) for c in letters) / len(letters) if letters else 0


ATTEMPTS = 2  # model output varies; the guard turns a rare ungrounded answer into a safe fallback, which is correct behaviour but fails the assertions below


def run_case(case, service, dataset, raw_rows):
    session = f"live-ar-{case['id']}-{uuid.uuid4()}"
    response = None
    for turn in case.get("conversation") or [case["question"]]:
        response = service.handle({"action": "ask", "prompt": turn, "locale": case["locale"]}, session)
        assert "error" not in response, response
    answer = response["answer"]
    assert answer and response["grounded"] is True
    calls = [{"records": response["records"], "no_match": q.get("no_match")} for q in response["queries"]]
    assert find_ungrounded(answer, dataset, calls) == []
    for rep in {r["sales_rep"] for r in raw_rows}:
        assert rep.lower() not in answer.lower()
    expect = dict(case["expect"])
    arabic_expected = expect.pop("arabic_answer")
    assert (arabic_share(answer) > 0.5) is arabic_expected, answer
    check(expect, response)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_arabic_sample_query(case, service, dataset, raw_rows):
    for attempt in range(ATTEMPTS):
        try:
            return run_case(case, service, dataset, raw_rows)
        except AssertionError:
            if attempt == ATTEMPTS - 1:
                raise
