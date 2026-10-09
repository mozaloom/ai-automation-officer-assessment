"""State and audit storage with conditional writes, so two workers can never process or execute the same email twice.

`MemoryStore` (tests, local runs) and `DynamoStore` (deployed) implement the same contract.
Single-table layout: PK `MSG#<id>`; SK `STATE` for the message, `AUDIT#<ts>#<n>` for its audit trail.
GSI1 = status index (`STATUS#<status>` / received time); GSI2 = feeds (`FEED#MSG` and `FEED#AUDIT`, by time).
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable, Optional, Protocol

from .models import Status


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def audit_id() -> str:
    """Sorts chronologically even for events in the same millisecond (nanosecond clock first, random tail for uniqueness)."""
    return f"{time.time_ns():020d}{secrets.token_hex(2)}"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Store(Protocol):
    def claim(self, message_id: str, item: dict) -> bool: ...
    def get(self, message_id: str) -> Optional[dict]: ...
    def transition(self, message_id: str, allowed_from: Iterable[Status], to: Status, updates: Optional[dict] = None, lease_until: Optional[str] = None) -> bool: ...
    def acquire(self, message_id: str, allowed_from: Iterable[Status], lease_until: str, now: str) -> bool: ...
    def update(self, message_id: str, updates: dict) -> None: ...
    def list_by_status(self, status: Status, limit: int = 50) -> list[dict]: ...
    def list_messages(self, limit: int = 100) -> list[dict]: ...
    def append_audit(self, message_id: str, event: dict) -> None: ...
    def list_audit(self, message_id: Optional[str] = None, limit: int = 100) -> list[dict]: ...


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


class MemoryStore:
    """Thread-safe in-memory store with the same atomicity guarantees as the DynamoDB one."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._audit: list[dict] = []

    def claim(self, message_id: str, item: dict) -> bool:
        with self._lock:
            if message_id in self._items:
                return False
            self._items[message_id] = {**item, "message_id": message_id}
            return True

    def get(self, message_id: str) -> Optional[dict]:
        with self._lock:
            item = self._items.get(message_id)
            return json.loads(json.dumps(item)) if item else None

    def transition(self, message_id, allowed_from, to, updates=None, lease_until=None) -> bool:
        with self._lock:
            item = self._items.get(message_id)
            if not item or item["status"] not in {s.value for s in allowed_from}:
                return False
            item.update(updates or {})
            item["status"] = to.value
            item["lease_until"] = lease_until
            return True

    def acquire(self, message_id, allowed_from, lease_until, now) -> bool:
        """PROCESSING with an expired lease counts as abandoned and may be taken over."""
        with self._lock:
            item = self._items.get(message_id)
            if not item:
                return False
            status = item["status"]
            expired = status == Status.PROCESSING.value and (item.get("lease_until") or "") < now
            if status not in {s.value for s in allowed_from} and not expired:
                return False
            item["status"] = Status.PROCESSING.value
            item["lease_until"] = lease_until
            item["attempts"] = int(item.get("attempts", 0)) + 1
            return True

    def update(self, message_id, updates) -> None:
        with self._lock:
            self._items[message_id].update(updates)

    def list_by_status(self, status, limit=50) -> list[dict]:
        with self._lock:
            rows = [i for i in self._items.values() if i["status"] == status.value]
        return json.loads(json.dumps(sorted(rows, key=lambda i: i.get("received_at", ""), reverse=True)[:limit]))

    def list_messages(self, limit=100) -> list[dict]:
        with self._lock:
            rows = list(self._items.values())
        return json.loads(json.dumps(sorted(rows, key=lambda i: i.get("received_at", ""), reverse=True)[:limit]))

    def append_audit(self, message_id, event) -> None:
        with self._lock:
            self._audit.append({"message_id": message_id, "at": iso(utcnow()), "id": audit_id(), **event})

    def list_audit(self, message_id=None, limit=100) -> list[dict]:
        with self._lock:
            rows = [a for a in self._audit if message_id is None or a["message_id"] == message_id]
        return json.loads(json.dumps(sorted(rows, key=lambda a: (a["at"], a["id"]), reverse=True)[:limit]))


class DynamoStore:
    def __init__(self, table_name: str, client: Any = None, region: str = "us-east-1") -> None:
        import boto3

        self._table = (client or boto3.resource("dynamodb", region_name=region)).Table(table_name)
        self._conditional_error: type[Exception] = self._table.meta.client.exceptions.ConditionalCheckFailedException

    @staticmethod
    def _pk(message_id: str) -> str:
        return f"MSG#{message_id}"

    def _item(self, message_id: str, item: dict) -> dict:
        status = item["status"]
        return {**json.loads(json.dumps(item), parse_float=Decimal), "pk": self._pk(message_id), "sk": "STATE", "message_id": message_id,
                "gsi1pk": f"STATUS#{status}", "gsi1sk": item.get("received_at", ""), "gsi2pk": "FEED#MSG", "gsi2sk": item.get("received_at", "")}

    def claim(self, message_id, item) -> bool:
        try:
            self._table.put_item(Item=self._item(message_id, item), ConditionExpression="attribute_not_exists(pk)")
            return True
        except self._conditional_error:
            return False

    def get(self, message_id) -> Optional[dict]:
        found = self._table.get_item(Key={"pk": self._pk(message_id), "sk": "STATE"}, ConsistentRead=True).get("Item")
        return _plain(found) if found else None

    def _set(self, updates: dict, extra: dict) -> tuple[str, dict, dict]:
        names, values, parts = {}, {}, []
        for i, (key, value) in enumerate({**updates, **extra}.items()):
            names[f"#k{i}"], values[f":v{i}"] = key, json.loads(json.dumps(value), parse_float=Decimal)
            parts.append(f"#k{i} = :v{i}")
        return "SET " + ", ".join(parts), names, values

    def transition(self, message_id, allowed_from, to, updates=None, lease_until=None) -> bool:
        expr, names, values = self._set({**(updates or {}), "status": to.value, "lease_until": lease_until}, {"gsi1pk": f"STATUS#{to.value}"})
        allowed = list(allowed_from)
        cond_vals = {f":a{i}": s.value for i, s in enumerate(allowed)}
        try:
            self._table.update_item(
                Key={"pk": self._pk(message_id), "sk": "STATE"}, UpdateExpression=expr,
                ConditionExpression="attribute_exists(pk) AND #st IN (" + ", ".join(cond_vals) + ")",
                ExpressionAttributeNames={**names, "#st": "status"}, ExpressionAttributeValues={**values, **cond_vals},
            )
            return True
        except self._conditional_error:
            return False

    def acquire(self, message_id, allowed_from, lease_until, now) -> bool:
        allowed = list(allowed_from)
        cond_vals = {f":a{i}": s.value for i, s in enumerate(allowed)}
        expired = "(#st = :proc AND lease_until < :now)"
        condition = "attribute_exists(pk) AND " + (f"(#st IN ({', '.join(cond_vals)}) OR {expired})" if cond_vals else expired)
        try:
            self._table.update_item(
                Key={"pk": self._pk(message_id), "sk": "STATE"},
                UpdateExpression="SET #st = :proc, lease_until = :lease, gsi1pk = :gpk ADD attempts :one",
                ConditionExpression=condition,
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={**cond_vals, ":proc": Status.PROCESSING.value, ":lease": lease_until, ":now": now, ":one": 1, ":gpk": f"STATUS#{Status.PROCESSING.value}"},
            )
            return True
        except self._conditional_error:
            return False

    def update(self, message_id, updates) -> None:
        expr, names, values = self._set(updates, {})
        self._table.update_item(Key={"pk": self._pk(message_id), "sk": "STATE"}, UpdateExpression=expr, ExpressionAttributeNames=names, ExpressionAttributeValues=values)

    def _query(self, index: str, pk_name: str, pk: str, limit: int, key_filter: Optional[Callable] = None) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        out = self._table.query(IndexName=index, KeyConditionExpression=Key(pk_name).eq(pk), ScanIndexForward=False, Limit=limit)
        return [_plain(i) for i in out.get("Items", [])]

    def list_by_status(self, status, limit=50) -> list[dict]:
        return self._query("gsi1", "gsi1pk", f"STATUS#{status.value}", limit)

    def list_messages(self, limit=100) -> list[dict]:
        return self._query("gsi2", "gsi2pk", "FEED#MSG", limit)

    def append_audit(self, message_id, event) -> None:
        at = iso(utcnow())
        uid = audit_id()
        item = json.loads(json.dumps({**event, "message_id": message_id, "at": at, "id": uid}), parse_float=Decimal)
        self._table.put_item(Item={**item, "pk": self._pk(message_id), "sk": f"AUDIT#{at}#{uid}", "gsi2pk": "FEED#AUDIT", "gsi2sk": f"{at}#{uid}"})

    def list_audit(self, message_id=None, limit=100) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        if message_id:
            out = self._table.query(KeyConditionExpression=Key("pk").eq(self._pk(message_id)) & Key("sk").begins_with("AUDIT#"), ScanIndexForward=False, Limit=limit)
            return [_plain(i) for i in out.get("Items", [])]
        return self._query("gsi2", "gsi2pk", "FEED#AUDIT", limit)
