"""Data contracts. The agent's output (`Triage`) is untrusted input: it is validated here, then resolved and checked by deterministic code."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Action(str, Enum):
    CREATE_TASK = "CREATE_TASK"
    UPDATE_TASK = "UPDATE_TASK"
    REPLY = "REPLY"
    IGNORE = "IGNORE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Status(str, Enum):
    """Processing state of one email. Transitions are enforced by conditional writes in the store."""

    PROCESSING = "PROCESSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    IGNORED = "IGNORED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


Priority = Literal["urgent", "high", "normal", "low"]


class Email(BaseModel):
    """A mailbox message as the pipeline sees it. `body` is kept short and never logged."""

    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1, max_length=512)  # Graph message id (immutable) or internet message id
    sender: str = Field(min_length=3, max_length=320)
    sender_name: str = ""
    to: list[str] = Field(default_factory=list)
    subject: str = Field(default="", max_length=998)
    body: str = Field(default="", max_length=20000)
    received_at: datetime
    conversation_id: Optional[str] = None
    has_attachments: bool = False


class TaskDraft(BaseModel):
    """Task fields exactly as the agent extracted them: free text, not yet mapped to ClickUp values."""

    model_config = ConfigDict(extra="ignore")
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=8000)
    assignee: Optional[str] = Field(default=None, max_length=320)  # name or email as written in the email
    priority: Optional[Priority] = None
    due_date: Optional[date] = None
    status: Optional[str] = Field(default=None, max_length=60)

    @field_validator("title", "description", "assignee", "status", "due_date", "priority", mode="before")
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:
        """Models often send "" or "null" for "not stated": that is None, never a value."""
        if isinstance(value, str):
            value = value.strip()
            return None if value.lower() in ("", "null", "none", "n/a", "unknown", "not specified") else value
        return value

    @field_validator("priority", mode="before")
    @classmethod
    def _priority_lower(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value


class ReplyDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    body: str = Field(min_length=1, max_length=6000)
    subject: Optional[str] = Field(default=None, max_length=998)
    to: list[str] = Field(default_factory=list)


class Triage(BaseModel):
    """What the agent returns for one email."""

    model_config = ConfigDict(extra="ignore")
    action: Action
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(default="", max_length=1200)
    task: Optional[TaskDraft] = None
    target_task_id: Optional[str] = Field(default=None, max_length=64)
    reply: Optional[ReplyDraft] = None
    missing_fields: list[str] = Field(default_factory=list)
    sensitive: bool = False
    sensitivity_reasons: list[str] = Field(default_factory=list)

    @field_validator("missing_fields", "sensitivity_reasons", mode="before")
    @classmethod
    def _as_list(cls, value: Any) -> Any:
        """The model sometimes returns {} or a bare string where a list belongs."""
        if value is None or value == {}:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, dict):
            return [str(k) for k in value]
        return value

    @field_validator("sensitive", mode="before")
    @classmethod
    def _as_bool(cls, value: Any) -> Any:
        if value is None or value == {} or value == []:
            return False
        if isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _as_number(cls, value: Any) -> Any:
        try:
            return float(value) if isinstance(value, str) else value
        except ValueError:
            return value

    @field_validator("target_task_id", mode="before")
    @classmethod
    def _id_as_text(cls, value: Any) -> Any:
        return None if value in (None, "", "null") else str(value)

    @model_validator(mode="after")
    def _action_has_its_payload(self) -> "Triage":
        """An action without what it needs degrades to HUMAN_REVIEW: a person decides. It is never executed, and never an error loop."""
        missing = (
            "task" if self.action == Action.CREATE_TASK and self.task is None
            else "target_task_id" if self.action == Action.UPDATE_TASK and (self.task is None or not self.target_task_id)
            else "reply" if self.action == Action.REPLY and self.reply is None
            else None
        )
        if missing:
            self.rationale = f"The agent chose {self.action.value} but gave no {missing}. {self.rationale}".strip()[:1200]
            self.missing_fields = [*self.missing_fields, missing]
            self.action = Action.HUMAN_REVIEW
        return self


class Member(BaseModel):
    id: str
    username: str = ""
    email: str = ""


class Match(BaseModel):
    """An existing ClickUp task that may be the same work as the email."""

    task_id: str
    name: str
    url: str = ""
    status: str = ""
    score: float
    exact_marker: bool = False  # the task was created from this very email


class ResolvedTask(BaseModel):
    """Task fields mapped to real ClickUp values by deterministic code. `None` means unknown: never a guess."""

    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_label: Optional[str] = None
    priority: Optional[int] = None  # ClickUp: 1 urgent, 2 high, 3 normal, 4 low
    priority_source: Literal["email", "configured_default", "none"] = "none"
    due_date: Optional[date] = None
    status: Optional[str] = None
    problems: list[str] = Field(default_factory=list)


class Proposal(BaseModel):
    """The action the system proposes (and, after review, executes). Stored with the message."""

    action: Action
    triage: Triage
    resolved: Optional[ResolvedTask] = None
    matches: list[Match] = Field(default_factory=list)
    route: Literal["auto", "review"]
    reasons: list[str] = Field(default_factory=list)
    version: int = 1
    edited_by: Optional[str] = None


class Principal(BaseModel):
    """The authenticated caller, taken from the verified Cognito token, never from the request body."""

    user_id: str
    email: str = ""
    groups: list[str] = Field(default_factory=list)
