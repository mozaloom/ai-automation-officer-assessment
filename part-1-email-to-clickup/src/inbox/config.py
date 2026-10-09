"""Policy and runtime settings. Policy values are explicit and reviewable: nothing is decided by the model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional

PRIORITY_NUMBERS = {"urgent": 1, "high": 2, "normal": 3, "low": 4}  # ClickUp's own numbering
MARKER = "[email:{}]"  # written into a created task's description so a retry can find a half-finished create


@dataclass(frozen=True)
class PolicyConfig:
    # Automatic CREATE_TASK needs all of these resolved; anything missing goes to a person.
    required_for_create: tuple[str, ...] = ("title", "description", "assignee")
    min_confidence: float = 0.7
    duplicate_high: float = 0.8  # at or above: the same work; below `duplicate_low`: unrelated; in between: ask a person
    duplicate_low: float = 0.5
    # The only value ever filled in on the agent's behalf. None = leave priority unset. Approved here, not by the model.
    default_priority: Optional[str] = "normal"
    # ClickUp gives a new task the list's FIRST status ("blocked" here), so a created task gets this explicit, approved status instead.
    default_status: Optional[str] = "to do"
    auto_send_replies: bool = False  # external replies always need approval unless this is switched on
    internal_domains: tuple[str, ...] = ("medgan.ai",)
    max_due_days: int = 365
    # Fields an UPDATE_TASK may change without a person. Changing the assignee always needs review.
    update_auto_fields: tuple[str, ...] = ("status", "due_date", "priority", "description")
    sensitive_keywords: tuple[str, ...] = (
        "legal", "lawsuit", "attorney", "terminate", "termination", "salary", "payroll", "confidential", "password",
        "wire transfer", "bank details", "refund", "gdpr", "breach", "harassment", "resign", "dismiss",
        "قضية", "محامي", "راتب", "سري",
    )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "PolicyConfig":
        env = os.environ if env is None else env
        base = cls()
        default = env.get("INBOX_DEFAULT_PRIORITY", base.default_priority or "")
        return cls(
            min_confidence=float(env.get("INBOX_MIN_CONFIDENCE", base.min_confidence)),
            duplicate_high=float(env.get("INBOX_DUPLICATE_HIGH", base.duplicate_high)),
            duplicate_low=float(env.get("INBOX_DUPLICATE_LOW", base.duplicate_low)),
            default_priority=default if default in PRIORITY_NUMBERS else None,
            default_status=env.get("INBOX_DEFAULT_STATUS", base.default_status or "") or None,
            auto_send_replies=env.get("INBOX_AUTO_SEND_REPLIES", "false").lower() == "true",
            internal_domains=tuple(d.strip().lower() for d in env.get("INBOX_INTERNAL_DOMAINS", ",".join(base.internal_domains)).split(",") if d.strip()),
        )


@dataclass(frozen=True)
class Settings:
    mailbox: str = "xpand@medgan.ai"
    outlook_mode: str = "sample"  # "sample" (fixture mailbox) or "graph" (Microsoft Graph)
    clickup_mode: str = "sample"  # "sample" (in-memory tasks) or "api" (ClickUp REST)
    table_name: str = ""
    clickup_secret_id: str = "xpand/inbox/clickup"  # JSON: {"token": "...", "list_id": "...", "team_id": "..."}
    graph_secret_id: str = "xpand/inbox/graph"  # JSON: {"tenant_id","client_id","refresh_token"}
    region: str = "us-east-1"
    model_id: str = "us.amazon.nova-2-lite-v1:0"
    gateway_url: str = ""
    agent_runtime_arn: str = ""
    reviewer_group: str = "inbox-reviewers"
    lease_seconds: int = 120
    sync_limit: int = 25
    body_excerpt_chars: int = 1500
    policy: PolicyConfig = field(default_factory=PolicyConfig)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        d = cls()
        return cls(
            mailbox=env.get("INBOX_MAILBOX", d.mailbox),
            outlook_mode=env.get("OUTLOOK_MODE", d.outlook_mode),
            clickup_mode=env.get("CLICKUP_MODE", d.clickup_mode),
            table_name=env.get("INBOX_TABLE", d.table_name),
            clickup_secret_id=env.get("CLICKUP_SECRET_ID", d.clickup_secret_id),
            graph_secret_id=env.get("GRAPH_SECRET_ID", d.graph_secret_id),
            region=env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION") or d.region,
            model_id=env.get("BEDROCK_MODEL_ID", d.model_id),
            gateway_url=env.get("INBOX_GATEWAY_URL", d.gateway_url),
            agent_runtime_arn=env.get("INBOX_AGENT_RUNTIME_ARN", d.agent_runtime_arn),
            reviewer_group=env.get("INBOX_REVIEWER_GROUP", d.reviewer_group),
            policy=PolicyConfig.from_env(env),
        )
