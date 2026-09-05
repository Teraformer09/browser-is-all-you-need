#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/android-sdk}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$ROOT_DIR/.deps/android_avd}"
export ADB_PATH="${ADB_PATH:-$ANDROID_SDK_ROOT/platform-tools/adb}"
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"
export ADB_SERIAL="${ADB_SERIAL:-emulator-5556}"
mkdir -p "$ANDROID_AVD_HOME" "$ROOT_DIR/artifacts/uber_clone_031"
if ! emulator -list-avds | grep -qx AndroidTask_API_33; then
  echo no | avdmanager create avd -n AndroidTask_API_33 -k "system-images;android-33;google_apis;x86_64" --device pixel_6
fi
if "$ADB_PATH" -s "$ADB_SERIAL" get-state >/dev/null 2>&1; then exit 0; fi
if [[ ! -e /dev/kvm ]]; then echo "Missing /dev/kvm; expose it to Docker." >&2; exit 2; fi
emulator -avd AndroidTask_API_33 -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -no-snapshot -ports 5556,5557 >"$ROOT_DIR/artifacts/uber_clone_031/emulator.log" 2>&1 &
"$ADB_PATH" -s "$ADB_SERIAL" wait-for-device
for _ in $(seq 1 180); do [[ "$("$ADB_PATH" -s "$ADB_SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d "\r")" == 1 ]] && exit 0; sleep 1; done
echo "Emulator boot timed out" >&2; exit 1
