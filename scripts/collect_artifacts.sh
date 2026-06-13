#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="${1:-artifacts/runs/manual_collect}"
ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"

mkdir -p "$RUN_DIR"

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
}

if command -v "$ADB_PATH" >/dev/null 2>&1 || [[ -x "$ADB_PATH" ]]; then
  adb_cmd shell screencap -p /sdcard/final_screen.png >/dev/null 2>&1 || true
  adb_cmd pull /sdcard/final_screen.png "$RUN_DIR/final_screen.png" >/dev/null 2>&1 || true
  adb_cmd logcat -d > "$RUN_DIR/logcat.txt" 2>/dev/null || true
fi

touch "$RUN_DIR/final_screen.png" "$RUN_DIR/emulator_run.mp4" "$RUN_DIR/logcat.txt"
echo "Collected artifacts in $RUN_DIR"
