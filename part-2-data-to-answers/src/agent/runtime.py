"""Amazon Bedrock AgentCore Runtime entrypoint.

Payloads: {"action": "ask", "prompt": "...", "locale": "en" | "ar"} or {"action": "dashboard", "filters": {...}}.
AgentCore passes the session id (X-Amzn-Bedrock-AgentCore-Runtime-Session-Id) in `context`.

`ask` streams Server-Sent Events (one JSON object per `data:` line, see service.ask_stream);
every other action answers with a single JSON document.
"""

from __future__ import annotations

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from config import Settings

from .logging_config import configure_logging
from .service import AvailabilityService

settings = Settings.from_env()
configure_logging(settings.log_level)
service = AvailabilityService(settings)

# API Gateway cannot add response headers to a streamed (proxy) response, so the runtime sets CORS itself.
app = BedrockAgentCoreApp(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_methods=["POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"],
            max_age=3600,
        )
    ]
)


@app.entrypoint
async def invoke(payload, context=None):
    session_id = getattr(context, "session_id", None)
    if isinstance(payload, dict) and payload.get("action", "ask") == "ask":
        return service.ask_stream(payload.get("prompt"), session_id or payload.get("session_id"), payload.get("locale"))
    return service.handle(payload, session_id)


if __name__ == "__main__":
    app.run()
