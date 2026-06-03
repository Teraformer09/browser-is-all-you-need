#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK_PATH="$ROOT_DIR/dummy_android_app/build/out/dummy-rl-app.apk"
ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
}

if [[ ! -f "$APK_PATH" ]]; then
  APK_PATH="$("$ROOT_DIR/scripts/build_dummy_apk.sh")"
fi

adb_cmd wait-for-device
INSTALL_OUTPUT="$(adb_cmd install -r "$APK_PATH" 2>&1)" || {
  if [[ "$INSTALL_OUTPUT" == *"INSTALL_FAILED_UPDATE_INCOMPATIBLE"* ]]; then
    adb_cmd uninstall com.primeintellect.dummyrl >/dev/null
    adb_cmd install "$APK_PATH"
  else
    echo "$INSTALL_OUTPUT" >&2
    exit 1
  fi
}
adb_cmd shell am start -W -S -n com.primeintellect.dummyrl/.MainActivity >/dev/null
echo "Installed and launched com.primeintellect.dummyrl"
