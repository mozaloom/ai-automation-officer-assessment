#!/usr/bin/env bash
# Wrapper: ./connect_outlook.sh --tenant-id <GUID> --client-id <GUID>   (see connect_outlook.py)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$ROOT/.venv/bin/python" "$(dirname "${BASH_SOURCE[0]}")/connect_outlook.py" "$@"
