"""Strands wrapper around the deterministic search.

The wrapper is thin on purpose: all matching logic lives in availability.py. Each call's
full result is also kept in `agent.state` (never shown to the model) so the API can return
the exact records the answer was based on.
"""

from __future__ import annotations

import json
from typing import Optional

from strands import tool
from strands.types.tools import ToolContext

from .availability import DataStore, query_availability as search

STATE_KEY = "tool_calls"


def make_query_tool(store: DataStore, max_records: int = 25):
    @tool(context=True)
    def query_availability(
        product_name: Optional[str] = None,
        pack_size: Optional[str] = None,
        city: Optional[str] = None,
        area: Optional[str] = None,
        store_name: Optional[str] = None,
        availability_status: Optional[str] = None,
        tool_context: ToolContext = None,
    ) -> dict:
        """Search the latest recorded POS availability data. Deterministic: same filters, same answer.

        Pass only the filters the user actually mentioned; every filter is optional.

        Args:
            product_name: The product name only, as the user wrote it, e.g. "Olive Oil Extra Virgin" or "tea". Do not put the size, city or status in it.
            pack_size: Pack size only, e.g. "3 L", "750 ml", "1 kg". Do not set it unless the user gave a size.
            city: City name, e.g. "Amman".
            area: Neighbourhood / area inside a city, e.g. "Abdoun".
            store_name: Store name, e.g. "Sameh Mall Abdoun".
            availability_status: One of "In Stock", "Low Stock", "Out of Stock". Set it ONLY when the user explicitly asked for that state; never add it on your own.

        Returns a JSON object with total_matches, records, status_counts, data_as_of, and, when
        relevant, "ambiguous" (ask the user to choose) or "no_match" (report it; do not widen).
        """
        result = search(
            store.get(),
            product_name=product_name,
            pack_size=pack_size,
            city=city,
            area=area,
            store_name=store_name,
            availability_status=availability_status,
            max_records=max_records,
        )
        if tool_context is not None:
            calls = list(tool_context.agent.state.get(STATE_KEY) or [])
            calls.append(result)
            tool_context.agent.state.set(STATE_KEY, calls)
        return {"status": "success", "content": [{"text": json.dumps(result, ensure_ascii=False)}]}

    return query_availability
