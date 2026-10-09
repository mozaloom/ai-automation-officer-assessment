"""Local commands.

  python -m inbox.cli check-clickup            read-only: list workspace members, list statuses and task count (uses the Secrets Manager secret)
  python -m inbox.cli process-samples [--real-clickup]
        run the 8 fixture emails through the REAL agent (Amazon Bedrock) and the real pipeline, with an in-memory store.
        By default ClickUp is a sample adapter; with --real-clickup it writes to the real list (auto-approved actions create real tasks).
"""

from __future__ import annotations

import argparse
import json
import sys

from .adapters.sample import SampleMail, SampleTasks
from .agent import BedrockTriager, local_tools
from .config import Settings
from .models import Principal
from .service import InboxService
from .store import MemoryStore
from .wiring import build_tasks


def check_clickup() -> int:
    tasks = build_tasks(Settings(clickup_mode="api"))
    members = tasks.list_members()
    print(f"workspace members: {[m.username or m.email for m in members]}")
    print(f"list statuses: {tasks.list_statuses()}")
    print(f"tasks in the list: {len(tasks.list_tasks())}")
    return 0


def process_samples(real_clickup: bool) -> int:
    settings = Settings(clickup_mode="api" if real_clickup else "sample")
    tasks = build_tasks(settings) if real_clickup else SampleTasks()
    svc = InboxService(settings, MemoryStore(), SampleMail(), tasks, BedrockTriager(settings, local_tools(settings)))
    result = svc.sync(Principal(user_id="cli", email="cli@local", groups=[settings.reviewer_group]))
    print(json.dumps(result))
    for m in svc.list_messages():
        print(f"{m['status']:15} {str(m['action']):13} {m['subject'][:50]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="inbox.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-clickup")
    p = sub.add_parser("process-samples")
    p.add_argument("--real-clickup", action="store_true")
    args = parser.parse_args()
    return check_clickup() if args.cmd == "check-clickup" else process_samples(args.real_clickup)


if __name__ == "__main__":
    sys.exit(main())
