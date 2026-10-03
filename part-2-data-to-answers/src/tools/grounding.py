"""Deterministic grounding check for agent answers.

The model writes the answer; this module verifies it. Every store name, JOD price and
shelf quantity in the text must come from the records the tool returned, and internal
fields (sales representatives) must never appear. Works for English and Arabic answers
(Arabic store names, "دينار", "وحدة", Arabic-Indic digits).
"""

from __future__ import annotations

import re
from typing import Iterable

from .availability import PosDataset
from .glossary import _DIGITS, get_glossary, norm_ar

_NUMBER = r"(\d+(?:\.\d+)?)"
_PRICE = re.compile(rf"jod\s*{_NUMBER}|{_NUMBER}\s*jod|(?:دينار|دنانير)\s*{_NUMBER}|{_NUMBER}\s*(?:دينار|دنانير)", re.IGNORECASE)
_QUANTITY = re.compile(r"(\d+)\s*(?:units?|pcs|pieces|وحدة|وحدات|قطعة|قطع)(?![\w])", re.IGNORECASE)


def allowed_stores(calls: Iterable[dict]) -> set[str]:
    """Stores the answer may name: returned records plus stores the tool itself suggested."""
    allowed: set[str] = set()
    for call in calls:
        allowed |= {r["store_name"] for r in call.get("records", [])}
        for hint in ((call.get("no_match") or {}).get("hints") or {}).values():
            allowed |= set(hint.get("suggestions", []))
            for other in hint.get("matches_other_field", []):
                allowed |= set(other.get("values", []))
    return allowed


def find_ungrounded(answer: str, dataset: PosDataset, calls: list[dict]) -> list[str]:
    """Return human-readable problems; an empty list means the answer is grounded."""
    problems: list[str] = []
    answer = answer.translate(_DIGITS)  # ٣٨ -> 38
    text = answer.lower()
    arabic_text = f" {norm_ar(answer)} "
    glossary = get_glossary()
    allowed = allowed_stores(calls)
    for store in dataset.values("store_name"):
        arabic = glossary.label("store_name", store)
        named = store.lower() in text or bool(arabic and f" {norm_ar(arabic)} " in arabic_text)
        if named and store not in allowed:
            problems.append(f"store '{store}' was not in the tool results")
    records = [r for call in calls for r in call.get("records", [])]
    prices = {round(float(r["shelf_price_jod"]), 2) for r in records}
    for match in _PRICE.findall(answer):
        value = float(next(group for group in match if group))
        if round(value, 2) not in prices:
            problems.append(f"price {value} JOD was not in the tool results")
    quantities = {int(r["quantity_on_shelf"]) for r in records}
    for match in _QUANTITY.findall(answer):
        if int(match) not in quantities:
            problems.append(f"quantity {match} was not in the tool results")
    for rep in {r.sales_rep for r in dataset.records}:
        if rep.lower() in text:
            problems.append("an internal field (sales representative) was mentioned")
            break
    return list(dict.fromkeys(problems))
