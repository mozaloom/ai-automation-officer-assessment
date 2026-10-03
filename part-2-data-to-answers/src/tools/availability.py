"""Deterministic POS availability search.

No LLM and no AWS calls live here: given a loaded dataset and structured filters it
returns the matching records plus explicit signals (ambiguous / no_match) that tell the
agent what it must do next. The same filters always give the same answer, which is what
makes the agent's replies auditable.
"""

from __future__ import annotations

import csv
import difflib
import io
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Iterable, Sequence

STATUSES = ("In Stock", "Low Stock", "Out of Stock")
_STATUS_RANK = {status: rank for rank, status in enumerate(STATUSES)}
_STATUS_ALIASES = {
    "in stock": "In Stock",
    "instock": "In Stock",
    "low stock": "Low Stock",
    "low": "Low Stock",
    "lowstock": "Low Stock",
    "out of stock": "Out of Stock",
    "out": "Out of Stock",
    "outofstock": "Out of Stock",
}
_REQUIRED_COLUMNS = (
    "store_id", "store_name", "store_type", "area", "city", "region", "sku", "product_name",
    "category", "pack_size", "quantity_on_shelf", "availability_status", "shelf_price_jod",
    "last_updated", "sales_rep",
)
_STOPWORDS = {"the", "a", "an", "of", "in", "for", "any"}
_PUBLIC_FIELDS = (
    "store_name", "store_type", "area", "city", "region", "product_name", "category",
    "pack_size", "quantity_on_shelf", "availability_status", "shelf_price_jod", "last_updated",
)
_LOCATION_FIELDS = ("city", "area", "store_name")


@dataclass(frozen=True)
class PosRecord:
    store_id: str
    store_name: str
    store_type: str
    area: str
    city: str
    region: str
    sku: str
    product_name: str
    category: str
    pack_size: str
    quantity_on_shelf: int
    availability_status: str
    shelf_price_jod: float
    last_updated: date
    sales_rep: str

    def to_public(self) -> dict:
        """Fields safe to show to marketing. `sales_rep` and internal ids are never exposed."""
        data = {name: getattr(self, name) for name in _PUBLIC_FIELDS}
        data["last_updated"] = self.last_updated.isoformat()
        return data


# --------------------------------------------------------------------------- normalisation


def norm(text: object) -> str:
    """Lower-case ASCII with single spaces; keeps dots so '1.5' survives."""
    value = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9.]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _tokens(text: str) -> set[str]:
    out = set()
    for token in norm(text).split():
        if token in _STOPWORDS:
            continue
        out.add(token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token)
    return out


_PACK_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>kg|kgs|kilo|kilos|kilogram|kilograms|g|gr|gm|gram|grams|"
    r"l|lt|ltr|liter|liters|litre|litres|ml|milliliter|milliliters|millilitre|millilitres|bag|bags)$"
)
_UNIT_FACTORS = {
    **dict.fromkeys(("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"), ("g", 1000.0)),
    **dict.fromkeys(("g", "gr", "gm", "gram", "grams"), ("g", 1.0)),
    **dict.fromkeys(("l", "lt", "ltr", "liter", "liters", "litre", "litres"), ("ml", 1000.0)),
    **dict.fromkeys(("ml", "milliliter", "milliliters", "millilitre", "millilitres"), ("ml", 1.0)),
    **dict.fromkeys(("bag", "bags"), ("bags", 1.0)),
}


def canonical_pack(text: object) -> str:
    """'3L', '3 litre' and '3000 ml' all become '3000 ml'; unknown shapes fall back to norm()."""
    value = norm(text)
    match = _PACK_RE.match(value.replace(" ", "")) or _PACK_RE.match(value)
    if not match:
        return value
    unit, factor = _UNIT_FACTORS[match["unit"]]
    return f"{float(match['num']) * factor:g} {unit}"


_EMBEDDED_PACK = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(kg|kgs|kilos?|kilograms?|grams?|gm|g|ml|l|lt|ltr|liters?|litres?|bags?)(?![a-z])", re.IGNORECASE
)


def split_embedded_pack(product: str) -> tuple[str | None, str | None]:
    """'3 L Sunflower Cooking Oil' -> ('Sunflower Cooking Oil', '3 L'). Models often glue the size to the name."""
    match = _EMBEDDED_PACK.search(product)
    if not match:
        return product, None
    name = re.sub(r"\s+", " ", (product[: match.start()] + " " + product[match.end():])).strip(" -,")
    return (name or None), f"{match.group(1)} {match.group(2)}"


def normalize_status(value: str) -> str | None:
    return _STATUS_ALIASES.get(norm(value).replace("-", " "))


# --------------------------------------------------------------------------- dataset


class DatasetError(ValueError):
    """The CSV does not have the expected shape."""


class PosDataset:
    def __init__(self, records: Sequence[PosRecord]):
        if not records:
            raise DatasetError("dataset is empty")
        self.records: tuple[PosRecord, ...] = tuple(records)
        self._values = {
            field: sorted({getattr(r, field) for r in self.records})
            for field in ("product_name", "pack_size", "city", "area", "store_name", "category", "store_type", "region")
        }
        self.as_of: date = max(r.last_updated for r in self.records)
        self.oldest: date = min(r.last_updated for r in self.records)

    def values(self, field: str) -> list[str]:
        return self._values[field]

    @classmethod
    def from_csv_text(cls, text: str) -> "PosDataset":
        reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
        missing = [c for c in _REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise DatasetError(f"missing columns: {', '.join(missing)}")
        records = []
        for line, row in enumerate(reader, start=2):
            try:
                status = row["availability_status"].strip()
                if status not in _STATUS_RANK:
                    raise ValueError(f"unknown availability_status {status!r}")
                records.append(
                    PosRecord(
                        store_id=row["store_id"].strip(),
                        store_name=row["store_name"].strip(),
                        store_type=row["store_type"].strip(),
                        area=row["area"].strip(),
                        city=row["city"].strip(),
                        region=row["region"].strip(),
                        sku=row["sku"].strip(),
                        product_name=row["product_name"].strip(),
                        category=row["category"].strip(),
                        pack_size=row["pack_size"].strip(),
                        quantity_on_shelf=int(row["quantity_on_shelf"]),
                        availability_status=status,
                        shelf_price_jod=float(row["shelf_price_jod"]),
                        last_updated=datetime.strptime(row["last_updated"].strip(), "%d/%m/%Y").date(),
                        sales_rep=row["sales_rep"].strip(),
                    )
                )
            except (ValueError, KeyError) as exc:
                raise DatasetError(f"line {line}: {exc}") from exc
        return cls(records)


class DataStore:
    """Holds the parsed dataset and reloads it after `ttl_seconds` (S3 object may be replaced)."""

    def __init__(self, loader: Callable[[], str], ttl_seconds: float = 300.0, clock: Callable[[], float] = time.monotonic):
        self._loader = loader
        self._ttl = ttl_seconds
        self._clock = clock
        self._dataset: PosDataset | None = None
        self._loaded_at = 0.0

    def get(self) -> PosDataset:
        now = self._clock()
        if self._dataset is None or now - self._loaded_at >= self._ttl:
            try:
                self._dataset = PosDataset.from_csv_text(self._loader())
                self._loaded_at = now
            except Exception:
                if self._dataset is None:
                    raise
                self._loaded_at = now - self._ttl + 30  # keep serving stale data, retry in 30 s
        return self._dataset


def local_loader(path) -> Callable[[], str]:
    def load() -> str:
        with open(path, encoding="utf-8-sig") as handle:
            return handle.read()

    return load


def s3_loader(bucket: str, key: str, client=None) -> Callable[[], str]:
    def load() -> str:
        s3 = client
        if s3 is None:
            import boto3

            s3 = boto3.client("s3")
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8-sig")

    return load


def store_from_settings(settings, s3_client=None) -> DataStore:
    loader = s3_loader(settings.data_bucket, settings.data_key, s3_client) if settings.data_bucket else local_loader(settings.data_path)
    return DataStore(loader, settings.cache_ttl_seconds)


# --------------------------------------------------------------------------- matching


def _match_text(query: str, candidates: Iterable[str]) -> set[str]:
    """Exact (normalised) match wins; otherwise substring or token-subset match."""
    q = norm(query)
    values = list(candidates)
    exact = {v for v in values if norm(v) == q}
    if exact:
        return exact
    q_tokens = _tokens(query)
    return {v for v in values if q and (q in norm(v) or (q_tokens and q_tokens <= _tokens(v)))}


def _match_product(query: str, products: Iterable[str]) -> tuple[set[str], bool]:
    """Returns (matches, exact). Several non-exact matches means the term is ambiguous."""
    q = norm(query)
    values = list(products)
    exact = {v for v in values if norm(v) == q}
    if exact:
        return exact, True
    q_tokens = _tokens(query)
    if not q_tokens:
        return set(), False
    return {v for v in values if q_tokens <= _tokens(v)}, False


def _match_pack(query: str, packs: Iterable[str]) -> set[str]:
    target = canonical_pack(query)
    return {p for p in packs if canonical_pack(p) == target}


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sort_key(record: PosRecord):
    return (_STATUS_RANK[record.availability_status], record.city, record.store_name, record.product_name, record.pack_size)


def _status_counts(records: Sequence[PosRecord]) -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}
    for record in records:
        counts[record.availability_status] += 1
    return counts


def _suggest(value: str, candidates: Sequence[str]) -> list[str]:
    by_norm = {norm(c): c for c in candidates}
    close = difflib.get_close_matches(norm(value), list(by_norm), n=3, cutoff=0.6)
    return [by_norm[c] for c in close]


def _other_field_hits(field: str, value: str, dataset: PosDataset) -> list[dict]:
    hits = []
    for other in ("product_name", "city", "area", "store_name"):
        if other == field:
            continue
        found = sorted(_match_text(value, dataset.values(other)))[:3]
        if found:
            hits.append({"field": other, "values": found})
    return hits


def query_availability(
    dataset: PosDataset,
    *,
    product_name: str | None = None,
    pack_size: str | None = None,
    city: str | None = None,
    area: str | None = None,
    store_name: str | None = None,
    availability_status: str | None = None,
    max_records: int = 25,
) -> dict:
    """Search POS availability. See module docstring; result shape is documented in the README."""
    filters = {
        key: cleaned
        for key, cleaned in (
            ("product_name", _clean(product_name)),
            ("pack_size", _clean(pack_size)),
            ("city", _clean(city)),
            ("area", _clean(area)),
            ("store_name", _clean(store_name)),
            ("availability_status", _clean(availability_status)),
        )
        if cleaned
    }
    if "product_name" in filters:
        name, embedded = split_embedded_pack(filters["product_name"])
        if embedded:
            filters.pop("product_name")
            if name:
                filters["product_name"] = name
            filters.setdefault("pack_size", embedded)
    base = {"filters_applied": dict(filters), "dataset_as_of": dataset.as_of.isoformat()}

    status = None
    if "availability_status" in filters:
        status = normalize_status(filters["availability_status"])
        if status is None:
            return {**base, "error": f"Unknown availability_status {filters['availability_status']!r}.", "allowed_statuses": list(STATUSES),
                    "total_matches": 0, "records": []}
        filters["availability_status"] = base["filters_applied"]["availability_status"] = status

    matched: dict[str, set[str]] = {}
    unmatched: list[str] = []

    if "product_name" in filters:
        products, exact = _match_product(filters["product_name"], dataset.values("product_name"))
        if len(products) > 1 and not exact and "pack_size" in filters:
            narrowed = {p for p in products if _match_pack(filters["pack_size"], {r.pack_size for r in dataset.records if r.product_name == p})}
            products = narrowed or products
        if len(products) > 1 and not exact:
            return {**base, "total_matches": 0, "records": [], "ambiguous": {"field": "product_name", "term": filters["product_name"], "candidates": sorted(products)},
                    "next_step": "ASK_CLARIFICATION: ask which of the candidate products the user means; do not guess."}
        (matched.__setitem__("product_name", products) if products else unmatched.append("product_name"))

    if "pack_size" in filters:
        pool = {r.pack_size for r in dataset.records if "product_name" not in matched or r.product_name in matched["product_name"]}
        packs = _match_pack(filters["pack_size"], pool)
        (matched.__setitem__("pack_size", packs) if packs else unmatched.append("pack_size"))

    for field in _LOCATION_FIELDS:
        if field in filters:
            values = _match_text(filters[field], dataset.values(field))
            (matched.__setitem__(field, values) if values else unmatched.append(field))

    if unmatched:
        hints = {}
        for field in unmatched:
            entry: dict = {"value": filters[field]}
            if field == "pack_size" and "product_name" in matched:
                entry["available_for_product"] = sorted({r.pack_size for r in dataset.records if r.product_name in matched["product_name"]})
            else:
                entry["suggestions"] = _suggest(filters[field], dataset.values(field))
                entry["matches_other_field"] = _other_field_hits(field, filters[field], dataset)
            hints[field] = entry
        return {**base, "total_matches": 0, "records": [], "no_match": {"reason": "unknown_filter_value", "unmatched_filters": unmatched, "hints": hints},
                "next_step": "REPORT_NO_MATCH: say the value was not found; offer the suggestions; do not search for something else without asking."}

    def select(skip: str | None = None) -> list[PosRecord]:
        out = []
        for record in dataset.records:
            if any(field != skip and getattr(record, field) not in values for field, values in matched.items()):
                continue
            if skip != "availability_status" and status and record.availability_status != status:
                continue
            out.append(record)
        return out

    selected = select()
    if not selected:
        options = []
        for field in [*matched, *(["availability_status"] if status else [])]:
            count = len(select(skip=field))
            if count:
                options.append({"drop_filter": field, "would_match": count})
        return {**base, "total_matches": 0, "records": [], "no_match": {"reason": "no_records_for_combination", "broader_options": options},
                "next_step": "REPORT_NO_MATCH: say nothing matches these exact filters; mention the broader options and ASK before widening the search."}

    selected.sort(key=_sort_key)
    shown = selected[:max_records]
    return {
        **base,
        "total_matches": len(selected),
        "returned": len(shown),
        "truncated": len(selected) > len(shown),
        "records": [r.to_public() for r in shown],
        "status_counts": _status_counts(selected),
        "pack_sizes_in_results": sorted({r.pack_size for r in selected}),
        "data_as_of": max(r.last_updated for r in selected).isoformat(),
        "oldest_update": min(r.last_updated for r in selected).isoformat(),
    }
