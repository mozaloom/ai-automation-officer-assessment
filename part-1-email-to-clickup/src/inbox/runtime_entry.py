"""AgentCore Runtime entrypoint for the Inbox Reviewer (IAM-authorized runtime, invoked by the inbox Lambda).

Payload: {"email": {...}, "context": {"members": [...], "statuses": [...], "tasks": [...]}} -> a Triage JSON (a proposal, nothing executed).
The model's tools come from the AgentCore Gateway (MCP, SigV4); they are read-only.
"""

from __future__ import annotations

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from .agent import BedrockTriager
from .config import Settings
from .models import Email
from .service import TriageUnavailable

settings = Settings.from_env()
logging.basicConfig(level=logging.INFO)
app = BedrockAgentCoreApp()


def _gateway_client():
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    return MCPClient(lambda: aws_iam_streamablehttp_client(endpoint=settings.gateway_url, aws_region=settings.region, aws_service="bedrock-agentcore"))


@app.entrypoint
def invoke(payload, context=None):
    try:
        email = Email.model_validate(payload["email"])
    except Exception:
        return {"error": {"code": "invalid_request", "message": "payload.email is not a valid email"}}
    ctx = payload.get("context") or {}
    try:
        if settings.gateway_url:
            with _gateway_client() as mcp:
                triage = BedrockTriager(settings, mcp.list_tools_sync()).triage(email, ctx)
        else:
            triage = BedrockTriager(settings, []).triage(email, ctx)
    except TriageUnavailable as err:
        return {"error": {"code": "unavailable", "message": str(err)}}  # the caller may retry
    except ValueError as err:
        return {"error": {"code": "invalid_proposal", "message": str(err)}}  # a clean answer, not an HTTP 500: the caller routes it to a person
    return triage.model_dump(mode="json")


if __name__ == "__main__":
    app.run()
