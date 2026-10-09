"""Deterministic mapping of the agent's free-text fields to real ClickUp values, and duplicate matching.

Nothing here guesses: an unknown assignee, status or invalid date comes back as None with a problem noted.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Iterable, Optional

from .config import MARKER, PRIORITY_NUMBERS, PolicyConfig
from .models import Match, Member, ResolvedTask, TaskDraft

_STOP = {"the", "a", "an", "of", "to", "for", "and", "in", "on", "by", "with", "please", "can", "you", "we", "need", "is", "are", "be", "this", "that", "it", "our", "my", "your", "task", "request"}


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "").lower()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^\w@.\-]+", " ", value).strip()


def tokens(text: str) -> set[str]:
    return {t for t in re.sub(r"[^\w]+", " ", _norm(text)).split() if t and t not in _STOP and len(t) > 1}


def similarity(a: str, b: str) -> float:
    """Overlap of meaningful words: the larger of Jaccard and containment of the shorter title (0 to 1)."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return round(max(inter / len(ta | tb), inter / min(len(ta), len(tb)) * 0.9), 3)


# --------------------------------------------------------------------------- assignee, priority, status, due date


def resolve_assignee(text: Optional[str], members: Iterable[Member]) -> tuple[Optional[Member], Optional[str]]:
    """Exact email, exact name, or a name part that identifies exactly one member. Otherwise unknown or ambiguous."""
    if not text or not text.strip():
        return None, "assignee missing"
    members = list(members)
    wanted = _norm(text)
    by_email = [m for m in members if m.email and _norm(m.email) == wanted]
    if len(by_email) == 1:
        return by_email[0], None
    by_name = [m for m in members if m.username and _norm(m.username) == wanted]
    if len(by_name) == 1:
        return by_name[0], None
    parts = tokens(text)
    if parts:
        hits = [m for m in members if parts <= tokens(m.username) | tokens(m.email.split("@")[0])]
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            return None, f"assignee '{text}' matches several members"
    return None, f"assignee '{text}' is not a member of the workspace"


def resolve_priority(value: Optional[str], config: PolicyConfig) -> tuple[Optional[int], str]:
    if value in PRIORITY_NUMBERS:
        return PRIORITY_NUMBERS[value], "email"
    if config.default_priority:
        return PRIORITY_NUMBERS[config.default_priority], "configured_default"
    return None, "none"


def resolve_status(value: Optional[str], statuses: Iterable[str]) -> tuple[Optional[str], Optional[str]]:
    if not value:
        return None, None
    for status in statuses:
        if status.lower() == value.strip().lower():
            return status, None
    return None, f"status '{value}' is not a status of the list"


def validate_due_date(value: Optional[date], received: date, config: PolicyConfig) -> tuple[Optional[date], Optional[str]]:
    if value is None:
        return None, None
    if value < received:
        return None, f"due date {value.isoformat()} is before the email was received"
    if value > received + timedelta(days=config.max_due_days):
        return None, f"due date {value.isoformat()} is more than {config.max_due_days} days away"
    return value, None


def resolve_task(draft: TaskDraft, members: Iterable[Member], statuses: Iterable[str], received: date, config: PolicyConfig, creating: bool = True) -> ResolvedTask:
    """`creating` controls the approved defaults (priority, status): they fill a NEW task only, never overwrite an existing one."""
    problems: list[str] = []
    member, problem = resolve_assignee(draft.assignee, members)
    if problem and draft.assignee:  # a missing assignee is not an error by itself; "required" is the policy's call
        problems.append(problem)
    status, problem = resolve_status(draft.status, statuses)
    if problem:
        problems.append(problem)
    due, problem = validate_due_date(draft.due_date, received, config)
    if problem:
        problems.append(problem)
    priority, source = resolve_priority(draft.priority, config) if (creating or draft.priority) else (None, "none")
    if creating and status is None and not draft.status and config.default_status:
        status, _ = resolve_status(config.default_status, statuses)  # approved default, only if the list really has that status
    return ResolvedTask(
        title=draft.title, description=draft.description,
        assignee_id=member.id if member else None, assignee_label=(member.username or member.email) if member else None,
        priority=priority, priority_source=source, due_date=due, status=status, problems=problems,
    )


# --------------------------------------------------------------------------- duplicates


def find_matches(title: str, message_id: str, candidates: Iterable[dict], limit: int = 5) -> list[Match]:
    """Existing tasks that look like the same work. A task created from this very email always scores 1.0."""
    marker = MARKER.format(message_id)
    out: list[Match] = []
    for task in candidates:
        exact = marker in (task.get("description") or "")
        score = 1.0 if exact else similarity(title, task.get("name", ""))
        if score > 0:
            out.append(Match(task_id=str(task["id"]), name=task.get("name", ""), url=task.get("url", ""), status=task.get("status", ""), score=score, exact_marker=exact))
    return sorted(out, key=lambda m: (-m.score, m.name))[:limit]
