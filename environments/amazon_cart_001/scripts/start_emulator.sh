#!/usr/bin/env bash
set -euo pipefail
: "${ANDROID_SDK_ROOT:?Set the Android SDK directory}"
: "${JAVA_HOME:?Set JDK 17 or later}"
: "${CART_AVD_HOME:?Set an empty task-owned AVD directory}"
export ANDROID_AVD_HOME="$CART_AVD_HOME"
export ANDROID_ADB_SERVER_PORT=5042
export ADB_SERVER_SOCKET=tcp:localhost:5042
if ss -ltn | awk '{print $4}' | grep -Eq ':(5042|5582|5583|8570)$'; then
  echo 'One of the dedicated shopping ports is in use; refusing to replace it.' >&2
  exit 1
fi
mkdir -p "$ANDROID_AVD_HOME"
if [ -e "$ANDROID_AVD_HOME/CartDemo_001.ini" ]; then
  echo 'Refusing to reuse an existing AVD. Choose a new empty directory.' >&2
  exit 1
fi
printf 'no\n' | "$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager" create avd \
 -n CartDemo_001 -k 'system-images;android-33;google_apis;x86_64' \
 -p "$ANDROID_AVD_HOME/device" --device pixel_6
"$ANDROID_SDK_ROOT/platform-tools/adb" -P 5042 start-server
exec "$ANDROID_SDK_ROOT/emulator/emulator" -avd CartDemo_001 \
 -no-window -no-audio -no-snapshot -no-boot-anim -gpu swiftshader_indirect \
 -ports 5582,5583 -grpc 8570 -grpc-use-jwt -memory 2048 -cores 2
