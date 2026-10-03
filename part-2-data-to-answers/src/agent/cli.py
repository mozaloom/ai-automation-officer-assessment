"""Local command line: python -m agent.cli "Where can I buy Olive Oil Extra Virgin in Amman?"."""

from __future__ import annotations

import argparse
import json
import uuid

from config import Settings

from .logging_config import configure_logging
from .service import AvailabilityService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Availability Agent locally (uses Bedrock + the local CSV).")
    parser.add_argument("question")
    parser.add_argument("--session", default=f"cli-{uuid.uuid4()}")
    parser.add_argument("--json", action="store_true", help="print the full JSON response")
    args = parser.parse_args()
    settings = Settings.from_env()
    configure_logging("WARNING")
    result = AvailabilityService(settings).handle({"action": "ask", "prompt": args.question}, args.session)
    if args.json or "error" in result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print(result["answer"])
    print(f"\n[{result['record_count']} matching records, data as of {result['data_as_of']}]")


if __name__ == "__main__":
    main()
