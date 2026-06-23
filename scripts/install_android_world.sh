#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ANDROID_WORLD_VENV:-$ROOT_DIR/.venv}"
ANDROID_WORLD_SRC="${ANDROID_WORLD_SRC:-$ROOT_DIR/third_party/android_world}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SDK_ROOT="${ANDROID_SDK_ROOT:-/data/Balram/android-sdk}"
JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$ROOT_DIR/.deps/android_avd}"
AVD_NAME="${ANDROID_WORLD_AVD_NAME:-AndroidWorld_API_33}"
AVD_DEVICE="${ANDROID_WORLD_AVD_DEVICE:-pixel_6}"
SYSTEM_IMAGE="${ANDROID_WORLD_SYSTEM_IMAGE:-system-images;android-33;google_apis;x86_64}"

export JAVA_HOME ANDROID_SDK_ROOT="$SDK_ROOT" ANDROID_HOME="$SDK_ROOT" ANDROID_AVD_HOME

find_sdk_tool() {
  local name="$1"
  if [[ -x "$SDK_ROOT/cmdline-tools/latest/bin/$name" ]]; then
    echo "$SDK_ROOT/cmdline-tools/latest/bin/$name"
  elif command -v "$name" >/dev/null 2>&1; then
    command -v "$name"
  else
    find /usr/lib/android-sdk/cmdline-tools "$SDK_ROOT/cmdline-tools" -path "*/bin/$name" -type f 2>/dev/null | sort -V | tail -1
  fi
}

SDKMANAGER="$(find_sdk_tool sdkmanager)"
AVDMANAGER="$(find_sdk_tool avdmanager)"
if [[ -z "$SDKMANAGER" || -z "$AVDMANAGER" ]]; then
  echo "sdkmanager/avdmanager not found. Install Android command-line tools first." >&2
  exit 1
fi

mkdir -p "$(dirname "$ANDROID_WORLD_SRC")" "$SDK_ROOT" "$ANDROID_AVD_HOME"

if [[ ! -d "$ANDROID_WORLD_SRC" ]]; then
  echo "Missing AndroidWorld source tree: $ANDROID_WORLD_SRC" >&2
  echo "Populate third_party/android_world before running this installer." >&2
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
"$VENV_DIR/bin/python" -m pip install "setuptools<81"
"$VENV_DIR/bin/python" -m pip install -r "$ANDROID_WORLD_SRC/requirements.txt"
"$VENV_DIR/bin/python" -m pip install --no-build-isolation -e "$ANDROID_WORLD_SRC"
"$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"

yes | "$SDKMANAGER" --sdk_root="$SDK_ROOT" --licenses >/dev/null || true
"$SDKMANAGER" --sdk_root="$SDK_ROOT" \
  "cmdline-tools;latest" \
  "platform-tools" \
  "emulator" \
  "platforms;android-33" \
  "platforms;android-34" \
  "$SYSTEM_IMAGE"

SDKMANAGER="$(find_sdk_tool sdkmanager)"
AVDMANAGER="$(find_sdk_tool avdmanager)"

EMULATOR_BIN="$SDK_ROOT/emulator/emulator"
if [[ ! -x "$EMULATOR_BIN" ]]; then
  echo "Android emulator binary missing after SDK install: $EMULATOR_BIN" >&2
  exit 1
fi

if ! "$EMULATOR_BIN" -list-avds | grep -qx "$AVD_NAME"; then
  echo "no" | "$AVDMANAGER" create avd \
    -n "$AVD_NAME" \
    -k "$SYSTEM_IMAGE" \
    --device "$AVD_DEVICE"
fi

"$VENV_DIR/bin/python" - <<'CHECKPY'
import android_world
print('android_world import ok')
CHECKPY

echo "AndroidWorld install ready"
echo "SDK_ROOT=$SDK_ROOT"
echo "ANDROID_AVD_HOME=$ANDROID_AVD_HOME"
echo "AVD_NAME=$AVD_NAME"
echo "ANDROID_WORLD_SRC=$ANDROID_WORLD_SRC"
