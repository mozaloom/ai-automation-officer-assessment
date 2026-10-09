"""Builds the adapters and the service for the configured mode (sample or real). Shared by the API Lambda, the tool Lambda and the CLI."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

from .adapters.base import AdapterError, MailAdapter, TaskAdapter
from .adapters.clickup import ClickUpAdapter
from .adapters.graph import GraphAdapter, SecretsManagerBox
from .adapters.sample import SampleMail, SampleTasks
from .config import Settings
from .service import InboxService, Triager
from .store import DynamoStore, MemoryStore, Store


@lru_cache(maxsize=4)
def _secret(secret_id: str, region: str) -> dict:
    import boto3

    try:
        return json.loads(boto3.client("secretsmanager", region_name=region).get_secret_value(SecretId=secret_id)["SecretString"])
    except Exception as err:
        raise AdapterError("clickup_not_configured", f"the ClickUp secret '{secret_id}' is not available ({type(err).__name__})") from None


def build_tasks(settings: Settings) -> TaskAdapter:
    if settings.clickup_mode == "api":
        return ClickUpAdapter.from_secret(_secret(settings.clickup_secret_id, settings.region))
    return SampleTasks()


def build_mail(settings: Settings) -> MailAdapter:
    if settings.outlook_mode == "graph":
        return GraphAdapter(SecretsManagerBox(settings.graph_secret_id, settings.region))
    return SampleMail()


def build_store(settings: Settings) -> Store:
    return DynamoStore(settings.table_name, region=settings.region) if settings.table_name else MemoryStore()


def build_service(settings: Settings, triager: Triager, store: Optional[Store] = None, mail: Optional[MailAdapter] = None, tasks: Optional[TaskAdapter] = None) -> InboxService:
    return InboxService(settings, store or build_store(settings), mail or build_mail(settings), tasks or build_tasks(settings), triager)
