#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIME_BIN="$ROOT/.local/bin/prime"

test -x "$PRIME_BIN" || {
  echo "Run ./scripts/bootstrap.sh first." >&2
  exit 1
}

exec "$PRIME_BIN" --plain env push \
  --path "$ROOT" \
  --name amazon-improved-task-001 \
  --visibility PUBLIC \
  --runtime v0
