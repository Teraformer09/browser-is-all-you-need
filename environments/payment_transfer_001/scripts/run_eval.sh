#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
: "${ADB_SERIAL:?Select the dedicated payment emulator}"
: "${OPENROUTER_API_KEY:?Supply OpenRouter credentials through the environment}"
exec "${PAYMENT_PYTHON:-python3}" -m payment_transfer_001.cli --confirm-eval \
 --serial "$ADB_SERIAL" --adb "${ADB_PATH:-adb}" \
 --apk "${PAYMENT_APK:-$ROOT/app/dummy_android_app/app/build/outputs/apk/debug/app-debug.apk}" \
 --output-dir "${PAYMENT_OUTPUT:-$ROOT/artifacts/model}" \
 --model "${PAYMENT_MODEL:-dots-studio/dots-3-note-preview:free}" "$@"
