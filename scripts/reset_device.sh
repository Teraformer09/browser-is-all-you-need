#!/usr/bin/env bash
set -euo pipefail

PACKAGE="${PACKAGE:-com.primeintellect.dummyrl}"
ACTIVITY="${ACTIVITY:-.MainActivity}"
ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
}

adb_cmd wait-for-device
adb_cmd shell am force-stop "$PACKAGE" || true
adb_cmd shell pm clear "$PACKAGE"
adb_cmd shell am start -W -S -n "$PACKAGE/$ACTIVITY" >/dev/null
echo "Reset $PACKAGE"
