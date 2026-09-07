#!/usr/bin/env bash
set -euo pipefail
: "${ANDROID_SDK_ROOT:?Set the Android SDK directory}"
: "${JAVA_HOME:?Set JDK 17 or later}"
: "${PAYMENT_AVD_HOME:?Set an empty task-owned AVD directory}"
export ANDROID_AVD_HOME="$PAYMENT_AVD_HOME"
export ANDROID_ADB_SERVER_PORT=5041
export ADB_SERVER_SOCKET=tcp:localhost:5041
if ss -ltn | awk '{print $4}' | grep -Eq ':(5041|5580|5581|8568)$'; then
  echo 'One of the dedicated payment ports is in use; refusing to replace it.' >&2
  exit 1
fi
mkdir -p "$ANDROID_AVD_HOME"
if [ -e "$ANDROID_AVD_HOME/PaymentEval_001.ini" ]; then
  echo 'Refusing to reuse an existing AVD. Choose a new empty directory.' >&2
  exit 1
fi
printf 'no\n' | "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager" create avd \
 -n PaymentEval_001 -k 'system-images;android-33;google_apis;x86_64' \
 -p "$ANDROID_AVD_HOME/device" --device pixel_6
"$ANDROID_SDK_ROOT/platform-tools/adb" -P 5041 start-server
exec "$ANDROID_SDK_ROOT/emulator/emulator" -avd PaymentEval_001 \
 -no-window -no-audio -no-snapshot -no-boot-anim -gpu swiftshader_indirect \
 -ports 5580,5581 -grpc 8568 -grpc-use-jwt -memory 2048 -cores 2
