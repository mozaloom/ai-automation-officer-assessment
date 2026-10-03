"""Request handling shared by the AgentCore entrypoint, the CLI and the local dev server."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import Callable

from config import Settings
from tools.analytics import dashboard
from tools.availability import DataStore, store_from_settings
from tools.grounding import find_ungrounded
from tools.strands_tool import STATE_KEY

from .agent import build_agent

log = logging.getLogger("availability")
MAX_RECORDS_IN_RESPONSE = 100
CORRECTION = (
    "Correction: your last answer contained information that is not in the query_availability results "
    "({problems}). Rewrite the answer using only values returned by the tool, copying quantities and "
    "prices exactly and naming only returned stores. Do not mention this correction."
)
FALLBACK = "I could not produce a fully verified summary for this question, so please rely on the matching records shown below."


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


class AvailabilityService:
    def __init__(self, settings: Settings, store: DataStore | None = None, agent_factory: Callable | None = None):
        self.settings = settings
        self.store = store or store_from_settings(settings)
        self._factory = agent_factory or (lambda: build_agent(settings, self.store))
        self._sessions: "OrderedDict[str, tuple[object, threading.Lock]]" = OrderedDict()
        self._guard = threading.Lock()

    # ------------------------------------------------------------------ routing

    def handle(self, payload, session_id: str | None = None) -> dict:
        if not isinstance(payload, dict):
            return _error("invalid_request", "Request body must be a JSON object.")
        action = payload.get("action", "ask")
        if action == "ask":
            return self.ask(payload.get("prompt"), session_id or payload.get("session_id"))
        if action == "dashboard":
            return self.dashboard(payload.get("filters") or {})
        return _error("invalid_request", f"Unknown action {action!r}.")

    # ------------------------------------------------------------------ dashboard

    def dashboard(self, filters: dict) -> dict:
        started = time.perf_counter()
        if not isinstance(filters, dict):
            return _error("invalid_request", "filters must be an object.")
        data = dashboard(self.store.get(), city=_str(filters.get("city")), category=_str(filters.get("category")), status=_str(filters.get("status")))
        log.info("dashboard", extra={"event": "dashboard", "filters": data["filters"], "listings": data["kpis"]["listings"], "latency_ms": _ms(started)})
        return data

    # ------------------------------------------------------------------ assistant

    def ask(self, prompt, session_id: str | None) -> dict:
        started = time.perf_counter()
        if not isinstance(prompt, str) or not prompt.strip():
            return _error("invalid_request", "Please type a question.")
        prompt = prompt.strip()
        if len(prompt) > self.settings.max_prompt_chars:
            return _error("invalid_request", f"Please keep the question under {self.settings.max_prompt_chars} characters.")
        sid = session_id if isinstance(session_id, str) and session_id else "anonymous"
        agent, lock = self._session(sid)
        with lock:
            agent.state.set(STATE_KEY, [])
            try:
                answer = str(agent(prompt)).strip()
            except Exception:
                log.exception("agent failed", extra={"event": "agent_error", "session": _hash(sid), "model_id": self.settings.model_id})
                return _error("agent_error", "The assistant could not answer right now. Please try again in a moment.")
            calls = list(agent.state.get(STATE_KEY) or [])
            problems = find_ungrounded(answer, self.store.get(), calls)
            if problems:  # guard: one corrective retry, then a safe fallback
                log.warning("ungrounded answer", extra={"event": "ungrounded", "session": _hash(sid), "problems": problems})
                try:
                    answer = str(agent(CORRECTION.format(problems="; ".join(problems)))).strip()
                except Exception:
                    log.exception("retry failed", extra={"event": "agent_error", "session": _hash(sid)})
                calls = list(agent.state.get(STATE_KEY) or [])
                problems = find_ungrounded(answer, self.store.get(), calls)
        if problems:
            answer = FALLBACK
        response = self._response(answer, calls, sid)
        response["grounded"] = not problems
        log.info(
            "ask",
            extra={
                "event": "ask", "session": _hash(sid), "prompt_chars": len(prompt), "tool_calls": len(calls),
                "filters": [c.get("filters_applied") for c in calls], "matches": [c.get("total_matches") for c in calls],
                "ambiguous": any("ambiguous" in c for c in calls), "no_match": any("no_match" in c for c in calls),
                "latency_ms": _ms(started), "model_id": self.settings.model_id,
            },
        )
        return response

    def _response(self, answer: str, calls: list[dict], sid: str) -> dict:
        seen, records = set(), []
        for call in calls:
            for record in call.get("records", []):
                key = (record["store_name"], record["product_name"], record["pack_size"])
                if key not in seen:
                    seen.add(key)
                    records.append(record)
        last = calls[-1] if calls else {}
        dataset = self.store.get()
        return {
            "answer": answer,
            "records": records[:MAX_RECORDS_IN_RESPONSE],
            "queries": [
                {"filters": c.get("filters_applied", {}), "total_matches": c.get("total_matches", 0), "status_counts": c.get("status_counts"),
                 "ambiguous": c.get("ambiguous"), "no_match": c.get("no_match")}
                for c in calls
            ],
            "record_count": sum(c.get("total_matches", 0) for c in calls),
            "data_as_of": last.get("data_as_of") or dataset.as_of.isoformat(),
            "session_id": sid,
        }

    def _session(self, sid: str):
        with self._guard:
            if sid in self._sessions:
                self._sessions.move_to_end(sid)
            else:
                self._sessions[sid] = (self._factory(), threading.Lock())
                while len(self._sessions) > self.settings.session_cache_size:
                    self._sessions.popitem(last=False)
            return self._sessions[sid]


def _str(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
