"""Request handling shared by the AgentCore entrypoint, the CLI and the local dev server."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from typing import AsyncIterator, Callable

from config import Settings
from tools.analytics import dashboard, records_view
from tools.availability import DataStore, store_from_settings
from tools.grounding import find_ungrounded
from tools.glossary import has_arabic
from tools.strands_tool import LANGUAGE_KEY, STATE_KEY

from .agent import build_agent

log = logging.getLogger("availability")
MAX_RECORDS_IN_RESPONSE = 100
CORRECTION = (
    "Correction: your last answer contained information that is not in the query_availability results "
    "({problems}). Rewrite the answer using only values returned by the tool, copying quantities and "
    "prices exactly and naming only returned stores. Do not mention this correction."
)
FALLBACK = "I could not produce a fully verified summary for this question, so please rely on the matching records shown below."
FALLBACK_AR = "تعذّر عليّ إعداد ملخّص موثّق لهذا السؤال، فيُرجى الاعتماد على السجلّات المطابقة المعروضة أدناه."
LOCALES = ("en", "ar")


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


class AvailabilityService:
    def __init__(self, settings: Settings, store: DataStore | None = None, agent_factory: Callable | None = None):
        self.settings = settings
        self.store = store or store_from_settings(settings)
        self._factory = agent_factory or (lambda: build_agent(settings, self.store))
        self._sessions: "OrderedDict[str, tuple[object, threading.Lock, asyncio.Lock]]" = OrderedDict()
        self._guard = threading.Lock()

    # ------------------------------------------------------------------ routing

    def handle(self, payload, session_id: str | None = None) -> dict:
        if not isinstance(payload, dict):
            return _error("invalid_request", "Request body must be a JSON object.")
        action = payload.get("action", "ask")
        if action == "ask":
            return self.ask(payload.get("prompt"), session_id or payload.get("session_id"), payload.get("locale"))
        if action == "dashboard":
            return self.dashboard(payload.get("filters") or {})
        if action == "records":
            return self.records(payload.get("filters") or {})
        return _error("invalid_request", f"Unknown action {action!r}.")

    # ------------------------------------------------------------------ dashboard

    def dashboard(self, filters: dict) -> dict:
        started = time.perf_counter()
        if not isinstance(filters, dict):
            return _error("invalid_request", "filters must be an object.")
        data = dashboard(self.store.get(), city=_str(filters.get("city")), category=_str(filters.get("category")), status=_str(filters.get("status")))
        log.info("dashboard", extra={"event": "dashboard", "filters": data["filters"], "listings": data["kpis"]["listings"], "latency_ms": _ms(started)})
        return data

    def records(self, filters: dict) -> dict:
        if not isinstance(filters, dict):
            return _error("invalid_request", "filters must be an object.")
        keys = ("city", "category", "status", "product", "store")
        return records_view(self.store.get(), **{k: _str(filters.get(k)) for k in keys})

    # ------------------------------------------------------------------ assistant

    def ask(self, prompt, session_id: str | None, locale: str | None = None) -> dict:
        started = time.perf_counter()
        prompt, invalid = self._check_prompt(prompt)
        if invalid:
            return invalid
        sid = _sid(session_id)
        agent, lock, _ = self._session(sid)
        locale = _locale(locale)
        with lock:
            agent.state.set(STATE_KEY, [])
            agent.state.set(LANGUAGE_KEY, _reply_language(prompt, locale))
            try:
                answer = str(agent(_message(prompt, locale))).strip()
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
            answer = _fallback(prompt, locale)
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

    def _check_prompt(self, prompt) -> tuple[str, dict | None]:
        if not isinstance(prompt, str) or not prompt.strip():
            return "", _error("invalid_request", "Please type a question.")
        prompt = prompt.strip()
        if len(prompt) > self.settings.max_prompt_chars:
            return "", _error("invalid_request", f"Please keep the question under {self.settings.max_prompt_chars} characters.")
        return prompt, None

    async def ask_stream(self, prompt, session_id: str | None, locale: str | None = None) -> AsyncIterator[dict]:
        """Stream one answer as events: start, status, records, delta, reset, replace, done, error.

        The deterministic grounding check runs on the finished text. A failed check resets the
        text, streams one corrective retry, and falls back to the records-only message.
        """
        started = time.perf_counter()
        prompt, invalid = self._check_prompt(prompt)
        if invalid:
            yield {"type": "error", **invalid["error"]}
            return
        sid = _sid(session_id)
        agent, _, lock = self._session(sid)
        locale = _locale(locale)
        async with lock:
            agent.state.set(STATE_KEY, [])
            agent.state.set(LANGUAGE_KEY, _reply_language(prompt, locale))
            yield {"type": "start", "session_id": sid}
            turn = _Turn()
            try:
                async for event in self._stream_turn(agent, _message(prompt, locale), turn):
                    yield event
                answer = turn.text
                calls = list(agent.state.get(STATE_KEY) or [])
                problems = find_ungrounded(answer, self.store.get(), calls)
                if problems:
                    log.warning("ungrounded answer", extra={"event": "ungrounded", "session": _hash(sid), "problems": problems})
                    yield {"type": "reset"}
                    retry = _Turn(sent=turn.sent)
                    try:
                        async for event in self._stream_turn(agent, CORRECTION.format(problems="; ".join(problems)), retry):
                            yield event
                        answer = retry.text
                    except Exception:
                        log.exception("retry failed", extra={"event": "agent_error", "session": _hash(sid)})
                    calls = list(agent.state.get(STATE_KEY) or [])
                    problems = find_ungrounded(answer, self.store.get(), calls)
                    turn = retry
            except Exception:
                log.exception("agent failed", extra={"event": "agent_error", "session": _hash(sid), "model_id": self.settings.model_id})
                yield {"type": "error", "code": "agent_error", "message": "The assistant could not answer right now. Please try again in a moment."}
                return
        if problems:
            answer = _fallback(prompt, locale)
        if answer != turn.streamed.strip():  # what the user sees must equal the final verified answer
            yield {"type": "replace", "text": answer}
        response = self._response(answer, calls, sid)
        response["grounded"] = not problems
        yield {"type": "done", **response}
        log.info(
            "ask",
            extra={
                "event": "ask", "session": _hash(sid), "prompt_chars": len(prompt), "tool_calls": len(calls),
                "filters": [c.get("filters_applied") for c in calls], "matches": [c.get("total_matches") for c in calls],
                "ambiguous": any("ambiguous" in c for c in calls), "no_match": any("no_match" in c for c in calls),
                "latency_ms": _ms(started), "model_id": self.settings.model_id, "streamed": True,
            },
        )

    async def _stream_turn(self, agent, message: str, turn: "_Turn") -> AsyncIterator[dict]:
        """Run one agent turn, translating Strands stream events into ours."""
        async for event in agent.stream_async(message):
            if not isinstance(event, dict):
                continue
            text = event.get("data")
            if isinstance(text, str) and text:
                turn.streamed += text
                yield {"type": "delta", "text": text}
            tool_use = event.get("current_tool_use")
            if isinstance(tool_use, dict) and tool_use.get("toolUseId") and tool_use["toolUseId"] not in turn.tools:
                turn.tools.add(tool_use["toolUseId"])
                if turn.streamed:  # preamble written before the tool call is not part of the final answer
                    turn.streamed = ""
                    yield {"type": "reset"}
                yield {"type": "status", "state": "searching"}
            if "result" in event:
                turn.text = str(event["result"]).strip()
            calls = agent.state.get(STATE_KEY) or []
            if len(calls) > turn.sent:
                turn.sent = len(calls)
                partial = self._response("", list(calls), "")
                yield {"type": "records", **{k: partial[k] for k in ("records", "queries", "record_count", "data_as_of")}}

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
                self._sessions[sid] = (self._factory(), threading.Lock(), asyncio.Lock())
                while len(self._sessions) > self.settings.session_cache_size:
                    self._sessions.popitem(last=False)
            return self._sessions[sid]


class _Turn:
    """Progress of one streamed agent turn."""

    def __init__(self, sent: int = 0):
        self.text = ""  # final text of the turn (from the agent result)
        self.streamed = ""  # text the client currently shows
        self.sent = sent  # number of tool calls already reported as `records`
        self.tools: set[str] = set()


def _locale(value) -> str | None:
    return value if value in LOCALES else None


def _message(prompt: str, locale: str | None) -> str:
    """The question as written. Only a question with no words (e.g. "12345") gets the interface language as a hint."""
    return f"{prompt}\n\n[interface_language: {locale}]" if locale and not any(c.isalpha() for c in prompt) else prompt


def _reply_language(prompt: str, locale: str | None) -> str:
    """The question's own language; the interface language only decides when the question has no words."""
    if has_arabic(prompt):
        return "ar"
    return "en" if any(c.isalpha() for c in prompt) else locale or "en"


def _fallback(prompt: str, locale: str | None) -> str:
    return FALLBACK_AR if _reply_language(prompt, locale) == "ar" else FALLBACK


def _sid(session_id) -> str:
    return session_id if isinstance(session_id, str) and session_id else "anonymous"


def _str(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
