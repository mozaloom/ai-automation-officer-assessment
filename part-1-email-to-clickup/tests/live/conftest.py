"""Live fixtures: REAL Amazon Bedrock and the REAL ClickUp list from AWS Secrets Manager. Outlook uses the sample mailbox (Graph is not connected yet).
Every task created during a test is deleted afterwards."""

import json

import boto3
import pytest

from inbox.adapters.base import http_json
from inbox.adapters.clickup import API, ClickUpAdapter
from inbox.adapters.sample import SampleMail
from inbox.agent import BedrockTriager, local_tools
from inbox.config import Settings
from inbox.models import Principal
from inbox.service import InboxService
from inbox.store import MemoryStore

REVIEWER = Principal(user_id="live-1", email="reviewer@medgan.ai", groups=["inbox-reviewers"])


@pytest.fixture(scope="session")
def secret():
    try:
        return json.loads(boto3.client("secretsmanager", region_name="us-east-1").get_secret_value(SecretId="xpand/inbox/clickup")["SecretString"])
    except Exception as err:  # pragma: no cover
        pytest.skip(f"ClickUp secret not available: {type(err).__name__}")


class TrackingClickUp(ClickUpAdapter):
    """Real adapter that remembers what it created so the test can clean up."""

    created_ids: list

    def create_task(self, fields):
        task = super().create_task(fields)
        self.created_ids.append(task["id"])
        return task


@pytest.fixture()
def live(secret):
    import os
    os.environ.update({"CLICKUP_MODE": "api"})
    clickup = TrackingClickUp.from_secret(secret)
    clickup.created_ids = []
    mail, store = SampleMail(emails=[]), MemoryStore()
    settings = Settings(clickup_mode="api", outlook_mode="sample")
    svc = InboxService(settings, store, mail, clickup, BedrockTriager(settings, local_tools(settings)))
    yield type("Live", (), {"svc": svc, "mail": mail, "tasks": clickup, "store": store})()
    for task_id in clickup.created_ids:
        http_json("DELETE", f"{API}/task/{task_id}", {"Authorization": secret["token"]})
