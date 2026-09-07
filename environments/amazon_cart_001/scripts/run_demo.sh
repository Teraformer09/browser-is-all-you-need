#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
: "${ADB_SERIAL:?Choose the dedicated shopping emulator}"
exec "${CART_PYTHON:-python3}" -m amazon_cart_001.agents.scripted --confirm-ui-run \
 --serial "$ADB_SERIAL" --adb "${ADB_PATH:-adb}" \
 --apk "$ROOT/app/shopping_android_app/app/build/outputs/apk/debug/app-debug.apk" \
 --output-dir "${CART_OUTPUT:-$ROOT/artifacts/ui_demo}" "$@"
