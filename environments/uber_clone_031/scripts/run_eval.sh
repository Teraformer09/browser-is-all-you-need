#!/usr/bin/env bash
set -euo pipefail
[[ "${ALLOW_UBER031_EVAL:-0}" == 1 ]] || { echo "Evaluation disabled. Ask for approval before setting ALLOW_UBER031_EVAL=1." >&2; exit 2; }
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ADB_SERIAL="${ADB_SERIAL:-emulator-5556}"
export RESET_MODE="${RESET_MODE:-full}"
export PYTHONPATH="$ROOT_DIR:${PYTHONPATH:-}"
bash "$ROOT_DIR/scripts/start_emulator.sh"
bash "$ROOT_DIR/scripts/install_apk.sh"
export UBER031_APK_PATH="$ROOT_DIR/app/dummy_android_app/build/out/dummy-rl-app.apk"
exec "${PYTHON_BIN:-python3}" -u -m uber_clone_031.cli \
  --confirm-eval \
  --policy "${POLICY:-scripted}" \
  --response-format "${RESPONSE_FORMAT:-text}" \
  --model "${MODEL:-minimax/minimax-m3:free}" \
  --output-dir "${OUTPUT_DIR:-$ROOT_DIR/artifacts/uber_clone_031}" "$@"
