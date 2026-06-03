#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK_PATH="$ROOT_DIR/dummy_android_app/build/out/dummy-rl-app.apk"

if [[ ! -f "$APK_PATH" ]]; then
  APK_PATH="$("$ROOT_DIR/scripts/build_dummy_apk.sh")"
fi

adb wait-for-device
INSTALL_OUTPUT="$(adb install -r "$APK_PATH" 2>&1)" || {
  if [[ "$INSTALL_OUTPUT" == *"INSTALL_FAILED_UPDATE_INCOMPATIBLE"* ]]; then
    adb uninstall com.primeintellect.dummyrl >/dev/null
    adb install "$APK_PATH"
  else
    echo "$INSTALL_OUTPUT" >&2
    exit 1
  fi
}
adb shell am start -W -S -n com.primeintellect.dummyrl/.MainActivity >/dev/null
echo "Installed and launched com.primeintellect.dummyrl"
