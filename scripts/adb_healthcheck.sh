#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"
PACKAGE_NAME="${PACKAGE_NAME:-com.primeintellect.dummyrl}"

ADB_PATH="$ADB_PATH" ADB_SERIAL="$ADB_SERIAL" "$ROOT_DIR/scripts/adb_wait_for_device.sh"

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
}

echo "serial=${ADB_SERIAL:-default}"
echo "api_level=$(adb_cmd shell getprop ro.build.version.sdk | tr -d '\r')"
echo "build_fingerprint=$(adb_cmd shell getprop ro.build.fingerprint | tr -d '\r')"
echo "screen_size=$(adb_cmd shell wm size | tr -d '\r')"
echo "screen_density=$(adb_cmd shell wm density | tr -d '\r')"
echo "boot_completed=$(adb_cmd shell getprop sys.boot_completed | tr -d '\r')"

if adb_cmd shell pm path "$PACKAGE_NAME" >/dev/null 2>&1; then
  echo "package_installed=true"
else
  echo "package_installed=false"
fi
