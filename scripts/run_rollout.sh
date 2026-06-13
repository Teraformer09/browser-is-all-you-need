#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="${ROLLOUT_BACKEND:-adb}"

cd "$ROOT_DIR"

python3 - <<'CHECKPY'
import importlib
importlib.import_module("android_adk_rl_env")
print("Python dependencies ok")
CHECKPY

ADB_PATH="${ADB_PATH:-adb}"
if ! command -v "$ADB_PATH" >/dev/null 2>&1 && [[ ! -x "$ADB_PATH" ]]; then
  echo "ADB is required for ROLLOUT_BACKEND=adb" >&2
  exit 1
fi
"$ADB_PATH" start-server >/dev/null
if ! "$ADB_PATH" devices | awk 'NR>1 && $2=="device" {found=1} END {exit !found}'; then
  echo "No connected Android device/emulator. Start an emulator before running the rollout suite." >&2
  exit 1
fi
./scripts/build_dummy_apk.sh >/dev/null
./scripts/install_dummy_apk.sh >/dev/null

python3 -B -m android_adk_rl_env.rollout_runner --backend "$BACKEND"
