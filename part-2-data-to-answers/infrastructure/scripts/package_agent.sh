#!/usr/bin/env bash
# Build build/agent.zip for AgentCore direct code deployment (linux/arm64, Python 3.13).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/build"
PKG="$BUILD/pkg"

rm -rf "$BUILD"
mkdir -p "$PKG"

# AgentCore Runtime is arm64 only: resolve wheels for that platform, not the local one.
uv pip install --quiet \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.13 \
  --only-binary=:all: \
  --target "$PKG" \
  -r "$ROOT/requirements-runtime.txt"

cp -r "$ROOT/src/agent" "$ROOT/src/tools" "$ROOT/src/config.py" "$PKG/"
cat > "$PKG/main.py" <<'PY'
from agent.runtime import app

if __name__ == "__main__":
    app.run()
PY

find "$PKG" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$PKG" -type d -exec chmod 755 {} +
find "$PKG" -type f -exec chmod 644 {} +

(cd "$PKG" && zip -qrX "$BUILD/agent.zip" .)
echo "built $BUILD/agent.zip ($(du -h "$BUILD/agent.zip" | cut -f1))"
