#!/usr/bin/env bash
# Build build/inbox-lambda.zip for the Part 1 Lambdas (inbox-api and inbox-tools): linux/arm64, Python 3.13.
# boto3 is part of the Lambda runtime; pydantic is bundled (compiled wheel for arm64).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PART1="$ROOT/../part-1-email-to-clickup"
PKG="$ROOT/build/inbox-pkg"

rm -rf "$PKG" "$ROOT/build/inbox-lambda.zip"
mkdir -p "$PKG"
uv pip install --quiet --python-platform aarch64-manylinux2014 --python-version 3.13 --only-binary=:all: --target "$PKG" "pydantic>=2.7,<3"
cp -r "$PART1/src/inbox" "$PKG/"
find "$PKG" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$PKG" -type d -exec chmod 755 {} + ; find "$PKG" -type f -exec chmod 644 {} +
(cd "$PKG" && zip -qrX "$ROOT/build/inbox-lambda.zip" .)
echo "built $ROOT/build/inbox-lambda.zip ($(du -h "$ROOT/build/inbox-lambda.zip" | cut -f1))"
