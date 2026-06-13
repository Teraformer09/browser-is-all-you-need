#!/usr/bin/env bash
set -euo pipefail

ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"
TIMEOUT_S="${TIMEOUT_S:-180}"

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
}

"$ADB_PATH" start-server >/dev/null
if [[ -n "$ADB_SERIAL" && "$ADB_SERIAL" == *:* ]]; then
  adb_cmd connect "$ADB_SERIAL" >/dev/null 2>&1 || true
fi
adb_cmd wait-for-device

deadline=$((SECONDS + TIMEOUT_S))
while (( SECONDS < deadline )); do
  booted="$(adb_cmd shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
  if [[ "$booted" == "1" ]]; then
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for Android device boot completion" >&2
exit 1
