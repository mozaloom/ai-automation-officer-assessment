"""Deterministic dashboard aggregates over the POS dataset (no LLM, no extra service).

Served by the same AgentCore runtime as the assistant (`action: "dashboard"`), so the
backend chain stays API Gateway -> AgentCore Runtime -> POS data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Sequence

from .availability import STATUSES, PosDataset, PosRecord, normalize_status

_KEYS = {"In Stock": "in_stock", "Low Stock": "low_stock", "Out of Stock": "out_of_stock"}
AT_RISK_LIMIT = 10


def _split(records: Iterable[PosRecord]) -> dict[str, int]:
    counts = Counter(r.availability_status for r in records)
    return {_KEYS[s]: counts.get(s, 0) for s in STATUSES}


def _grouped(records: Sequence, field: str) -> list[dict]:
    groups: dict[str, list[PosRecord]] = defaultdict(list)
    for record in records:
        groups[getattr(record, field)].append(record)
    rows = [{field: key, **_split(rs), "total": len(rs)} for key, rs in groups.items()]
    return sorted(rows, key=lambda row: (-row["total"], row[field]))


def _pct(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def dashboard(dataset: PosDataset, *, city: str | None = None, category: str | None = None, status: str | None = None) -> dict:
    """Aggregates for the dashboard. Filters narrow the data; `options` always lists every choice."""
    filters: dict[str, str] = {}
    records = list(dataset.records)
    if city:
        match = next((c for c in dataset.values("city") if c.lower() == city.strip().lower()), None)
        records = [r for r in records if match and r.city == match]
        filters["city"] = city.strip()
    if category:
        match = next((c for c in dataset.values("category") if c.lower() == category.strip().lower()), None)
        records = [r for r in records if match and r.category == match]
        filters["category"] = category.strip()
    if status:
        wanted = normalize_status(status)
        records = [r for r in records if wanted and r.availability_status == wanted]
        filters["status"] = wanted or status.strip()

    total = len(records)
    split = _split(records)
    at_risk = []
    by_product: dict[str, list[PosRecord]] = defaultdict(list)
    for record in records:
        by_product[record.product_name].append(record)
    for product, rs in by_product.items():
        parts = _split(rs)
        risk = parts["low_stock"] + parts["out_of_stock"]
        if risk:
            at_risk.append({
                "product_name": product,
                "category": rs[0].category,
                "low_stock": parts["low_stock"],
                "out_of_stock": parts["out_of_stock"],
                "at_risk": risk,
                "listings": len(rs),
                "at_risk_pct": _pct(risk, len(rs)),
            })
    at_risk.sort(key=lambda row: (-row["at_risk"], -row["out_of_stock"], row["product_name"]))

    stores: dict[str, list[PosRecord]] = defaultdict(list)
    for record in records:
        stores[record.store_name].append(record)
    risky_stores = []
    for store, rs in stores.items():
        parts = _split(rs)
        risk = parts["low_stock"] + parts["out_of_stock"]
        if risk:
            risky_stores.append({"store_name": store, "city": rs[0].city, "area": rs[0].area, "low_stock": parts["low_stock"],
                                 "out_of_stock": parts["out_of_stock"], "at_risk": risk, "listings": len(rs)})
    risky_stores.sort(key=lambda row: (-row["at_risk"], -row["out_of_stock"], row["store_name"]))

    freshness = Counter(r.last_updated.isoformat() for r in records)
    return {
        "filters": filters,
        "as_of": max((r.last_updated for r in records), default=dataset.as_of).isoformat(),
        "oldest_update": min((r.last_updated for r in records), default=dataset.oldest).isoformat(),
        "dataset_as_of": dataset.as_of.isoformat(),
        "options": {"cities": dataset.values("city"), "categories": dataset.values("category"), "statuses": list(STATUSES)},
        "kpis": {
            "listings": total,
            "stores": len({r.store_id for r in records}),
            "products": len({r.product_name for r in records}),
            "cities": len({r.city for r in records}),
            **split,
            "in_stock_pct": _pct(split["in_stock"], total),
            "low_stock_pct": _pct(split["low_stock"], total),
            "out_of_stock_pct": _pct(split["out_of_stock"], total),
        },
        "status_split": [{"status": s, "count": split[_KEYS[s]], "pct": _pct(split[_KEYS[s]], total)} for s in STATUSES],
        "by_city": _grouped(records, "city"),
        "by_category": _grouped(records, "category"),
        "by_store_type": _grouped(records, "store_type"),
        "at_risk_products": at_risk[:AT_RISK_LIMIT],
        "at_risk_stores": risky_stores[:AT_RISK_LIMIT],
        "freshness": [{"date": d, "count": n} for d, n in sorted(freshness.items())],
    }
