"""Amazon Bedrock AgentCore Runtime entrypoint.

Payloads: {"action": "ask", "prompt": "..."} or {"action": "dashboard", "filters": {...}}.
AgentCore passes the session id (X-Amzn-Bedrock-AgentCore-Runtime-Session-Id) in `context`.
"""

from __future__ import annotations

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from config import Settings

from .logging_config import configure_logging
from .service import AvailabilityService

settings = Settings.from_env()
configure_logging(settings.log_level)
service = AvailabilityService(settings)
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context=None):
    return service.handle(payload, getattr(context, "session_id", None))


if __name__ == "__main__":
    app.run()
