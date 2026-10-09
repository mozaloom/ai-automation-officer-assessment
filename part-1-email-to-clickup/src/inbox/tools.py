"""The MCP tool surface the model may use, exposed through an AgentCore Gateway Lambda target.

Minimal and READ-ONLY by design: the model can search and read ClickUp tasks, nothing else. It cannot read other emails (the one being
triaged is already in its prompt), cannot write to the mailbox (the backend creates reply drafts), and cannot create or update tasks or send
mail: those happen only in the backend, after policy and approval, so no prompt can talk its way into an external action.
Event = tool arguments; the tool name arrives in context.client_context.custom['bedrockAgentCoreToolName'] as '<target>___<tool>'.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .adapters.base import AdapterError
from .config import Settings
from .resolve import similarity
from .wiring import build_tasks

log = logging.getLogger("inbox.tools")

TOOL_SCHEMAS = [
    {"name": "clickup_search_tasks", "description": "Search the assessment ClickUp list for tasks whose title is similar to the query. Use it before proposing CREATE_TASK or UPDATE_TASK. Returns id, name, status, assignees, url.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Words from the task title to look for"}, "limit": {"type": "integer", "description": "Maximum results (1 to 10)"}}, "required": ["query"]}},
    {"name": "clickup_get_task", "description": "Read one ClickUp task by id: name, status, assignees, priority, due date, short description.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
]


def _brief(task: dict) -> dict:
    return {"id": task["id"], "name": task["name"], "status": task["status"], "assignees": task.get("assignees", []), "url": task.get("url", ""),
            "priority": task.get("priority"), "due_date": task.get("due_date"), "description": (task.get("description") or "")[:240]}


def make_tools(settings: Settings) -> dict[str, Callable[[dict], Any]]:
    tasks = build_tasks(settings)

    def search(args: dict) -> dict:
        query, limit = str(args.get("query", "")).strip(), max(1, min(int(args.get("limit", 5) or 5), 10))
        scored = sorted(((similarity(query, t["name"]), t) for t in tasks.list_tasks()), key=lambda x: -x[0])
        return {"tasks": [{**_brief(t), "match": s} for s, t in scored if s > 0][:limit]}

    return {
        "clickup_search_tasks": search,
        "clickup_get_task": lambda a: _brief(tasks.get_task(str(a["task_id"]))),
    }


_tools: dict | None = None


def handler(event: dict, context: Any) -> dict:
    """Lambda entry for the Gateway target. Returns plain JSON; tool errors are returned as {"error": ...} so the model can react."""
    global _tools
    name = (getattr(getattr(context, "client_context", None), "custom", None) or {}).get("bedrockAgentCoreToolName", "")
    name = name.split("___", 1)[-1]
    _tools = _tools or make_tools(Settings.from_env())
    if name not in _tools:
        return {"error": f"unknown tool '{name}'"}
    try:
        return _tools[name](event or {})
    except AdapterError as err:
        log.warning("tool failed", extra={"tool": name, "code": err.code})
        return {"error": err.code, "retryable": err.retryable}
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid arguments"}
