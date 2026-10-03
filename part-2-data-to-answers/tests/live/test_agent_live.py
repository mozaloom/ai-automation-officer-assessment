"""Real Amazon Bedrock calls against the real CSV. Run: pytest -m live (needs AWS credentials).

Each answer is checked three ways: the tool signals (records / ambiguous / no_match), the
records returned, and *grounding*: every store, price and quantity written in the answer must
exist in the records the tool returned.
"""

import json
import re
import uuid
from pathlib import Path

import boto3
import pytest

from agent.service import AvailabilityService
from config import Settings

pytestmark = pytest.mark.live
CASES = json.loads((Path(__file__).resolve().parents[1] / "sample_queries.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def service():
    if boto3.Session().get_credentials() is None:
        pytest.skip("no AWS credentials")
    return AvailabilityService(Settings.from_env())


@pytest.fixture(scope="module")
def all_stores(raw_rows):
    return {r["store_name"] for r in raw_rows}


@pytest.fixture(scope="module")
def sales_reps(raw_rows):
    return {r["sales_rep"] for r in raw_rows}


def assert_grounded(answer, response, all_stores, sales_reps):
    text = answer.lower()
    allowed = {r["store_name"] for r in response["records"]}
    for query in response["queries"]:
        for hint in ((query.get("no_match") or {}).get("hints") or {}).values():
            allowed |= set(hint.get("suggestions", []))
            for other in hint.get("matches_other_field", []):
                allowed |= set(other["values"])
    for store in all_stores:
        if store.lower() in text:
            assert store in allowed, f"answer names {store!r} but the tool never returned it"
    prices = {round(r["shelf_price_jod"], 2) for r in response["records"]}
    for match in re.findall(r"jod\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*jod", text):
        value = float(match[0] or match[1])
        assert round(value, 2) in prices, f"price {value} not in returned records"
    quantities = {r["quantity_on_shelf"] for r in response["records"]}
    for match in re.findall(r"(\d+)\s*(?:units|pcs|pieces)\b", text):
        assert int(match) in quantities, f"quantity {match} not in returned records"
    for rep in sales_reps:
        assert rep.lower() not in text, "answer leaked a sales representative"


def check(expect, response):
    queries = response["queries"]
    records = response["records"]
    if "records" in expect:
        assert bool(records) is expect["records"], f"records={len(records)}"
    if "ambiguous" in expect:
        assert any(q.get("ambiguous") for q in queries) is expect["ambiguous"]
    if "no_match" in expect:
        assert any(q.get("no_match") for q in queries) is expect["no_match"]
    if "tool_calls" in expect:
        assert len(queries) == expect["tool_calls"]
    for field, value in (expect.get("filters_include") or {}).items():
        assert any(value in str(q["filters"].get(field, "")).lower() for q in queries), f"no query filtered {field}~{value}"
    for field, value in (expect.get("all_records") or {}).items():
        assert records and all(str(r[field]).lower() == value.lower() for r in records), f"a record violates {field}={value}"
    if expect.get("records_cities_include"):
        assert set(expect["records_cities_include"]) <= {r["city"] for r in records}
    answer = response["answer"].lower()
    if expect.get("answer_contains_any"):
        assert any(s in answer for s in expect["answer_contains_any"]), answer
    for needle in expect.get("answer_contains_all", []):
        assert needle in answer
    for needle in expect.get("answer_not_contains", []):
        assert needle not in answer


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_sample_query(case, service, all_stores, sales_reps):
    session = f"live-{case['id']}-{uuid.uuid4()}"
    turns = case.get("conversation") or [case["question"]]
    response = None
    for turn in turns:
        response = service.handle({"action": "ask", "prompt": turn}, session)
        assert "error" not in response, response
    assert response["answer"]
    assert_grounded(response["answer"], response, all_stores, sales_reps)
    check(case["expect"], response)
