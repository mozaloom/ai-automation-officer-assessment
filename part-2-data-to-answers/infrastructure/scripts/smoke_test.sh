#!/usr/bin/env bash
# Quick proof that the deployment works: API contract tests + the public site responds.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
cd "$ROOT"
.venv/bin/python -m pytest -m e2e tests/e2e -q
URL="$(output WebUrl)"
echo "GET $URL/login/ -> $(curl -s -o /dev/null -w '%{http_code}' "$URL/login/")"
