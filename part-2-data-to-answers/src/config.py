"""Runtime configuration, read once from environment variables.

Everything has a safe default so the code runs locally against the bundled CSV.
In AgentCore the CDK stack sets DATA_S3_BUCKET / DATA_S3_KEY and the model id.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "pos_availability.csv"


@dataclass(frozen=True)
class Settings:
    model_id: str = DEFAULT_MODEL_ID
    region: str = "us-east-1"
    data_bucket: str = ""  # when set, the CSV is read from S3
    data_key: str = "pos_availability.csv"
    data_path: Path = DEFAULT_DATA_PATH  # local fallback / tests
    cache_ttl_seconds: float = 300.0
    max_records: int = 25  # records returned to the agent / UI per query
    max_prompt_chars: int = 500
    session_cache_size: int = 64
    max_output_tokens: int = 1500
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        defaults = cls()
        return cls(
            model_id=env.get("BEDROCK_MODEL_ID", defaults.model_id),
            region=env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION") or defaults.region,
            data_bucket=env.get("DATA_S3_BUCKET", defaults.data_bucket),
            data_key=env.get("DATA_S3_KEY", defaults.data_key),
            data_path=Path(env.get("DATA_LOCAL_PATH", str(defaults.data_path))),
            cache_ttl_seconds=float(env.get("DATA_CACHE_TTL_SECONDS", defaults.cache_ttl_seconds)),
            max_records=int(env.get("MAX_RECORDS", defaults.max_records)),
            max_prompt_chars=int(env.get("MAX_PROMPT_CHARS", defaults.max_prompt_chars)),
            session_cache_size=int(env.get("SESSION_CACHE_SIZE", defaults.session_cache_size)),
            max_output_tokens=int(env.get("MAX_OUTPUT_TOKENS", defaults.max_output_tokens)),
            log_level=env.get("LOG_LEVEL", defaults.log_level).upper(),
        )
