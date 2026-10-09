"""One contract, two implementations: the in-memory store and the DynamoDB store (moto) must behave identically."""

import threading

import boto3
import pytest
from moto import mock_aws

from inbox.models import Status
from inbox.store import DynamoStore, MemoryStore


def create_table():
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="inbox", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk")],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[
            {"IndexName": "gsi1", "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"}, {"AttributeName": "gsi1sk", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}},
            {"IndexName": "gsi2", "KeySchema": [{"AttributeName": "gsi2pk", "KeyType": "HASH"}, {"AttributeName": "gsi2sk", "KeyType": "RANGE"}], "Projection": {"ProjectionType": "ALL"}},
        ],
    )
    return ddb


@pytest.fixture(params=["memory", "dynamo"])
def store(request):
    if request.param == "memory":
        yield MemoryStore()
        return
    with mock_aws():
        create_table()
        yield DynamoStore("inbox", region="us-east-1")


def item(status="PROCESSING", received="2026-10-05T08:30:00.000Z", **kw):
    return {"status": status, "received_at": received, "lease_until": "2026-10-05T09:00:00.000Z", "attempts": 1, "subject": "s", **kw}


def test_claim_is_exclusive(store):
    assert store.claim("a", item()) and not store.claim("a", item())
    assert store.get("a")["subject"] == "s" and store.get("missing") is None


def _real_dynamodb_only(store):
    if isinstance(store, DynamoStore):
        pytest.skip("moto is not atomic under threads; real DynamoDB conditional writes are verified by tests/e2e/test_dynamo_atomicity.py")


def test_claim_is_exclusive_under_concurrency(store):
    _real_dynamodb_only(store)
    wins = []
    threads = [threading.Thread(target=lambda: wins.append(store.claim("race", item()))) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert wins.count(True) == 1


def test_transition_is_conditional_on_the_current_state(store):
    store.claim("a", item())
    assert not store.transition("a", [Status.PENDING_REVIEW], Status.EXECUTING)
    assert store.transition("a", [Status.PROCESSING], Status.PENDING_REVIEW, {"proposal": {"action": "REPLY", "n": 1.5}})
    assert store.get("a")["status"] == "PENDING_REVIEW" and store.get("a")["proposal"] == {"action": "REPLY", "n": 1.5}
    assert not store.transition("nope", [Status.PROCESSING], Status.EXECUTING)


def test_only_one_of_many_concurrent_transitions_wins(store):
    _real_dynamodb_only(store)
    store.claim("a", item(status="PENDING_REVIEW"))
    wins = []
    threads = [threading.Thread(target=lambda: wins.append(store.transition("a", [Status.PENDING_REVIEW], Status.EXECUTING))) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert wins.count(True) == 1


def test_acquire_takes_over_only_an_expired_lease_or_an_allowed_state(store):
    store.claim("a", item())
    assert not store.acquire("a", [], "2026-10-05T09:10:00.000Z", now="2026-10-05T08:59:00.000Z")  # lease still valid
    assert store.acquire("a", [], "2026-10-05T09:20:00.000Z", now="2026-10-05T09:01:00.000Z")  # expired
    assert store.get("a")["attempts"] == 2
    store.claim("f", item(status="FAILED"))
    assert store.acquire("f", [Status.FAILED], "2026-10-05T09:20:00.000Z", now="2026-10-05T08:00:00.000Z") and store.get("f")["status"] == "PROCESSING"
    assert not store.acquire("missing", [Status.FAILED], "x", now="y")


def test_listing_by_status_and_recent_first(store):
    store.claim("a", item(received="2026-10-05T08:00:00.000Z"))
    store.claim("b", item(status="PENDING_REVIEW", received="2026-10-06T08:00:00.000Z"))
    store.claim("c", item(status="PENDING_REVIEW", received="2026-10-07T08:00:00.000Z"))
    assert [i["message_id"] for i in store.list_by_status(Status.PENDING_REVIEW)] == ["c", "b"]
    assert [i["message_id"] for i in store.list_messages()] == ["c", "b", "a"]
    store.transition("b", [Status.PENDING_REVIEW], Status.EXECUTED)
    assert [i["message_id"] for i in store.list_by_status(Status.PENDING_REVIEW)] == ["c"]  # the status index follows the transition


def test_update_and_audit_trail(store):
    store.claim("a", item())
    store.update("a", {"draft": {"draft_id": "d1"}})
    assert store.get("a")["draft"] == {"draft_id": "d1"}
    store.append_audit("a", {"event": "received"})
    store.append_audit("a", {"event": "triaged", "outcome": "auto"})
    store.append_audit("b", {"event": "received"})
    assert [e["event"] for e in store.list_audit("a")] == ["triaged", "received"]
    assert {e["message_id"] for e in store.list_audit()} == {"a", "b"} and len(store.list_audit()) == 3
