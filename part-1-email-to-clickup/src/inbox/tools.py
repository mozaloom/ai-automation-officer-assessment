"""The MCP tool surface the model may use, exposed through an AgentCore Gateway Lambda target.

READ-ONLY by design: the model can search and read tasks, read an email and create a reply draft. It can NOT create or update tasks or send
mail: those happen only in the backend, after policy and approval, so no prompt can talk its way into an external write.
Event = tool arguments; the tool name arrives in context.client_context.custom['bedrockAgentCoreToolName'] as '<target>___<tool>'.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from .adapters.base import AdapterError
from .config import Settings
from .resolve import similarity
from .wiring import build_mail, build_tasks

log = logging.getLogger("inbox.tools")

TOOL_SCHEMAS = [
    {"name": "clickup_search_tasks", "description": "Search the assessment ClickUp list for tasks whose title is similar to the query. Use it before proposing CREATE_TASK or UPDATE_TASK. Returns id, name, status, assignees, url.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Words from the task title to look for"}, "limit": {"type": "integer", "description": "Maximum results (1 to 10)"}}, "required": ["query"]}},
    {"name": "clickup_get_task", "description": "Read one ClickUp task by id: name, status, assignees, priority, due date, short description.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "outlook_get_email", "description": "Read one email from the mailbox by message id (sender, subject, received time, body text).",
     "inputSchema": {"type": "object", "properties": {"message_id": {"type": "string"}}, "required": ["message_id"]}},
    {"name": "outlook_draft_reply", "description": "Create a reply DRAFT in the mailbox. Never sends. A person approves and sends.",
     "inputSchema": {"type": "object", "properties": {"message_id": {"type": "string"}, "body": {"type": "string"}}, "required": ["message_id", "body"]}},
]


def _brief(task: dict) -> dict:
    return {"id": task["id"], "name": task["name"], "status": task["status"], "assignees": task.get("assignees", []), "url": task.get("url", ""),
            "priority": task.get("priority"), "due_date": task.get("due_date"), "description": (task.get("description") or "")[:240]}


def make_tools(settings: Settings) -> dict[str, Callable[[dict], Any]]:
    tasks, mail = build_tasks(settings), build_mail(settings)

    def search(args: dict) -> dict:
        query, limit = str(args.get("query", "")).strip(), max(1, min(int(args.get("limit", 5) or 5), 10))
        scored = sorted(((similarity(query, t["name"]), t) for t in tasks.list_tasks()), key=lambda x: -x[0])
        return {"tasks": [{**_brief(t), "match": s} for s, t in scored if s > 0][:limit]}

    def get_email(args: dict) -> dict:
        e = mail.get_email(str(args["message_id"]))
        return {"sender": e.sender, "subject": e.subject, "received_at": e.received_at.isoformat(), "body": e.body[:3000]}

    return {
        "clickup_search_tasks": search,
        "clickup_get_task": lambda a: _brief(tasks.get_task(str(a["task_id"]))),
        "outlook_get_email": get_email,
        "outlook_draft_reply": lambda a: mail.draft_reply(str(a["message_id"]), str(a["body"])[:6000]),
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
