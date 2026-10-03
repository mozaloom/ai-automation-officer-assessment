"""Strands Availability Agent on Amazon Bedrock."""

from __future__ import annotations

from strands import Agent
from strands.models import BedrockModel

from config import Settings
from tools.availability import DataStore
from tools.strands_tool import STATE_KEY, make_query_tool

from .prompts import SYSTEM_PROMPT


def build_agent(settings: Settings, store: DataStore) -> Agent:
    model = BedrockModel(
        model_id=settings.model_id,
        region_name=settings.region,
        temperature=0.1,
        max_tokens=settings.max_output_tokens,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[make_query_tool(store, settings.max_records)],
        callback_handler=None,  # no console streaming inside the runtime
        state={STATE_KEY: []},
    )
