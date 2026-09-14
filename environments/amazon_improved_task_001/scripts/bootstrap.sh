#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="$ROOT/.cache/uv"
export UV_PROJECT_ENVIRONMENT="$ROOT/.venv"
export UV_TOOL_DIR="$ROOT/.local/uv-tools"
export UV_TOOL_BIN_DIR="$ROOT/.local/bin"

command -v uv >/dev/null 2>&1 || {
  echo "Missing uv. Install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
}

mkdir -p "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR"
uv sync --extra dev --project "$ROOT"
uv tool install --force prime==0.6.35

echo "Bootstrap complete. Prime CLI: $UV_TOOL_BIN_DIR/prime"
