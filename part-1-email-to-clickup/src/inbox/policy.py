"""The decision between "run automatically" and "ask a person". Pure functions: no model, no network, no clock."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .config import PolicyConfig
from .models import Action, Email, Match, Proposal, ResolvedTask, Triage


@dataclass
class Decision:
    route: str  # "auto" or "review"
    action: Action
    reasons: list[str] = field(default_factory=list)


def sensitive_hits(email: Email, config: PolicyConfig) -> list[str]:
    text = f"{email.subject}\n{email.body}".lower()
    return [k for k in config.sensitive_keywords if re.search(rf"(?<!\w){re.escape(k)}", text)]


def is_external(address: str, config: PolicyConfig) -> bool:
    domain = address.rsplit("@", 1)[-1].lower()
    return domain not in config.internal_domains


def decide(triage: Triage, email: Email, resolved: Optional[ResolvedTask], matches: list[Match], config: PolicyConfig) -> Decision:
    """First matching rule wins. Anything doubtful is a review, never a guess."""
    action = triage.action
    if action == Action.IGNORE:
        return Decision("auto", action, ["informational: no action needed"])
    if action == Action.HUMAN_REVIEW:
        return Decision("review", action, triage.missing_fields and [f"missing: {', '.join(triage.missing_fields)}"] or [triage.rationale or "the agent asked for a person to look at it"])

    reasons: list[str] = []
    hits = sensitive_hits(email, config)
    if triage.sensitive or hits:
        reasons.append("sensitive content" + (f" ({', '.join(hits[:3])})" if hits else "") + (": " + "; ".join(triage.sensitivity_reasons[:2]) if triage.sensitivity_reasons else ""))
    if triage.confidence < config.min_confidence:
        reasons.append(f"low confidence ({triage.confidence:.2f} < {config.min_confidence:.2f})")

    if action == Action.REPLY:
        recipients = triage.reply.to if triage.reply and triage.reply.to else [email.sender]
        if not config.auto_send_replies:
            reasons.append("replies need approval before sending")
        elif any(is_external(r, config) for r in recipients):
            reasons.append("external recipient needs approval")
        return Decision("review" if reasons else "auto", action, reasons)

    if resolved is None:
        reasons.append("no task fields")
        return Decision("review", action, reasons)
    for problem in resolved.problems:
        reasons.append(problem)

    best = matches[0] if matches else None
    if action == Action.CREATE_TASK:
        missing = [f for f in config.required_for_create if not _present(f, resolved)]
        if missing:
            reasons.append(f"missing {', '.join(missing)}")
        if best and best.score >= config.duplicate_high:
            reasons.append(f"likely duplicate of '{best.name}' ({best.score:.0%} match)")
        elif best and best.score >= config.duplicate_low:
            reasons.append(f"possible duplicate of '{best.name}' ({best.score:.0%} match)")
    elif action == Action.UPDATE_TASK:
        target = next((m for m in matches if m.task_id == triage.target_task_id), None)
        if target is None:
            reasons.append("the task the agent wants to update was not found by search")
        elif target.score < config.duplicate_high:
            reasons.append(f"unsure this is the same task ({target.score:.0%} match with '{target.name}')")
        changed = _changed_fields(triage)
        if not changed:
            reasons.append("nothing to change")
        blocked = [f for f in changed if f not in config.update_auto_fields]
        if blocked:
            reasons.append(f"changing {', '.join(blocked)} needs approval")
    return Decision("review" if reasons else "auto", action, reasons)


def _present(field_name: str, resolved: ResolvedTask) -> bool:
    return {"title": bool(resolved.title), "description": bool(resolved.description), "assignee": bool(resolved.assignee_id)}.get(field_name, False)


def _changed_fields(triage: Triage) -> list[str]:
    t = triage.task
    if t is None:
        return []
    # the title only identifies the task; it is not a change
    out = [name for name in ("description", "assignee", "priority", "due_date", "status") if getattr(t, name) is not None]
    return out
