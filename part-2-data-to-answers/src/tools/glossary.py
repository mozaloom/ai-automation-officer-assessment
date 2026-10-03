"""Arabic <-> English vocabulary for the POS data (glossary.json is the single source of truth).

The dataset stays in English. This module lets people ask in Arabic (MSA or Jordanian dialect):
Arabic names and aliases resolve to the canonical English values *deterministically*, so the
same question gives the same records however the model phrased its tool call. It also supplies
Arabic labels so answers use the established names for stores, areas and products.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable

GLOSSARY_PATH = Path(__file__).with_name("glossary.json")
LOCATION_PREFIXES = ("ب", "في", "ل")  # "بعمان" (in Amman), "لإربد" (to Irbid): written attached to the place name

_ARABIC = re.compile(r"[\u0600-\u06FF]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
_MARKS = re.compile(r"[\u064B-\u065F\u0670\u0640]")  # tashkeel and tatweel
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_NUMBER_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*([^\d\s.]+)")


def has_arabic(text: object) -> bool:
    return bool(_ARABIC.search(str(text)))


def _strip_article(token: str) -> str:
    return token[2:] if token.startswith("ال") and len(token) > 4 else token


def norm_ar(text: object) -> str:
    """Spelling-insensitive form: no diacritics, one alef/ya/ha variant, no 'al-', Western digits."""
    value = unicodedata.normalize("NFKC", str(text)).translate(_DIGITS).lower()
    value = _MARKS.sub("", value).translate(_LETTERS)
    value = re.sub(r"[^\w.]+", " ", value).replace("_", " ")
    return " ".join(_strip_article(token) for token in value.split())


def _drop_prefix(token: str) -> str:
    for prefix in LOCATION_PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix):]
    return token


class Glossary:
    def __init__(self, data: dict):
        self.version = data.get("version", 1)
        self._ar: dict[str, dict[str, str]] = {}
        self._names: dict[str, dict[str, set[str]]] = {}  # field -> canonical -> normalised Arabic names/aliases
        for field, entries in data.items():
            if not isinstance(entries, dict) or field in ("version", "note"):
                continue
            self._ar[field] = {canonical: entry["ar"] for canonical, entry in entries.items()}
            self._names[field] = {
                canonical: {norm_ar(name) for name in [entry["ar"], *entry.get("aliases", [])]} - {""}
                for canonical, entry in entries.items()
            }

    # ------------------------------------------------------------------ lookups

    def label(self, field: str, canonical: str) -> str | None:
        return self._ar.get(field, {}).get(canonical)

    def candidates(self, field: str, query: str) -> tuple[set[str], bool]:
        """Canonical values the Arabic `query` can mean, and whether one matched by exact name/alias."""
        names = self._names.get(field, {})
        q = norm_ar(query)
        if not q:
            return set(), False
        exact = {canonical for canonical, options in names.items() if q in options}
        if exact:
            return exact, True
        for variant in dict.fromkeys((q, " ".join(_drop_prefix(t) for t in q.split()))):
            tokens = set(variant.split())
            found = {canonical for canonical, options in names.items() if any(tokens <= set(option.split()) for option in options)}
            if found:
                return found, False
            if field in ("city", "area", "store_name"):  # a place written with a filler word: "فرع عمان"
                found = {canonical for canonical, options in names.items() if any(f" {option} " in f" {variant} " for option in options)}
                if found:
                    return found, False
        return set(), False

    def status(self, text: str) -> str | None:
        """Longest matching alias wins, so "غير متوفر" (out of stock) is not read as "متوفر" (in stock)."""
        q = f" {norm_ar(text)} "
        hits = [(len(option), canonical) for canonical, options in self._names.get("status", {}).items() for option in options if f" {option} " in q]
        return max(hits)[1] if hits else None

    def pack(self, text: str) -> str | None:
        """'٥ كيلو' / '5 كغم' -> '5 kg'; None when the text is not a recognisable size."""
        match = _NUMBER_UNIT.search(norm_ar(text))
        if not match:
            return None
        unit = match.group(2)
        for canonical, options in self._names.get("unit", {}).items():
            if unit in options:
                return f"{match.group(1)} {canonical}"
        return None

    def suggest(self, field: str, query: str, limit: int = 3) -> list[str]:
        by_name = {name: canonical for canonical, options in self._names.get(field, {}).items() for name in options}
        close = difflib.get_close_matches(norm_ar(query), list(by_name), n=limit * 2, cutoff=0.6)
        return list(dict.fromkeys(by_name[name] for name in close))[:limit]

    # ------------------------------------------------------------------ labels for answers

    def pack_label(self, pack: str) -> str | None:
        match = re.match(r"^(\d+(?:\.\d+)?)\s*(\w+)$", pack.strip())
        unit = self.label("unit", match.group(2)) if match else None
        return f"{match.group(1)} {unit}" if match and unit else None

    def labels_for(self, values: Iterable[str]) -> dict[str, str]:
        """English value -> Arabic label for every value we have a label for."""
        out: dict[str, str] = {}
        for value in values:
            if not isinstance(value, str) or value in out:
                continue
            label = next((self._ar[f][value] for f in self._ar if f != "unit" and value in self._ar[f]), None) or self.pack_label(value)
            if label:
                out[value] = label
        return out


@lru_cache(maxsize=1)
def get_glossary() -> Glossary:
    return Glossary(json.loads(GLOSSARY_PATH.read_text(encoding="utf-8")))
