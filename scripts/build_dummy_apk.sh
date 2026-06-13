#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/dummy_android_app"
BUILD_DIR="$APP_DIR/build"
SDK_ROOT="${ANDROID_SDK_ROOT:-/data/Balram/android-sdk}"
DEFAULT_BUILD_TOOLS="$SDK_ROOT/build-tools/34.0.0"
if [[ ! -x "$DEFAULT_BUILD_TOOLS/aapt" && -x "/usr/lib/android-sdk/build-tools/34.0.0/aapt" ]]; then
  DEFAULT_BUILD_TOOLS="/usr/lib/android-sdk/build-tools/34.0.0"
fi
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$DEFAULT_BUILD_TOOLS}"
ANDROID_JAR="${ANDROID_JAR:-$SDK_ROOT/platforms/android-34/android.jar}"
KEYSTORE_CACHE="$APP_DIR/debug.keystore"

AAPT="$BUILD_TOOLS/aapt"
D8="$BUILD_TOOLS/d8"
ZIPALIGN="$BUILD_TOOLS/zipalign"
APKSIGNER="$BUILD_TOOLS/apksigner"

if [[ ! -f "$ANDROID_JAR" ]]; then
  echo "Missing android.jar: $ANDROID_JAR" >&2
  echo "Install it with:" >&2
  echo "  JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sdkmanager --sdk_root=$SDK_ROOT 'platforms;android-34'" >&2
  exit 1
fi

if [[ -f "$BUILD_DIR/keys/debug.keystore" && ! -f "$KEYSTORE_CACHE" ]]; then
  cp "$BUILD_DIR/keys/debug.keystore" "$KEYSTORE_CACHE"
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/generated" "$BUILD_DIR/classes" "$BUILD_DIR/dex" "$BUILD_DIR/keys" "$BUILD_DIR/out"

"$AAPT" package \
  -f \
  -m \
  -J "$BUILD_DIR/generated" \
  -M "$APP_DIR/AndroidManifest.xml" \
  -S "$APP_DIR/res" \
  -I "$ANDROID_JAR"

find "$APP_DIR/src" "$BUILD_DIR/generated" -name '*.java' | sort > "$BUILD_DIR/sources.txt"

javac \
  -source 8 \
  -target 8 \
  -bootclasspath "$ANDROID_JAR" \
  -classpath "$ANDROID_JAR" \
  -d "$BUILD_DIR/classes" \
  @"$BUILD_DIR/sources.txt"

"$D8" \
  --min-api 23 \
  --output "$BUILD_DIR/dex" \
  $(find "$BUILD_DIR/classes" -name '*.class' | sort)

"$AAPT" package \
  -f \
  -M "$APP_DIR/AndroidManifest.xml" \
  -S "$APP_DIR/res" \
  -I "$ANDROID_JAR" \
  -F "$BUILD_DIR/out/dummy-unsigned.apk"

(cd "$BUILD_DIR/dex" && zip -q "$BUILD_DIR/out/dummy-unsigned.apk" classes.dex)

"$ZIPALIGN" -f -p 4 "$BUILD_DIR/out/dummy-unsigned.apk" "$BUILD_DIR/out/dummy-aligned.apk"

KEYSTORE="$BUILD_DIR/keys/debug.keystore"
if [[ -f "$KEYSTORE_CACHE" ]]; then
  cp "$KEYSTORE_CACHE" "$KEYSTORE"
fi

if [[ ! -f "$KEYSTORE" ]]; then
  keytool \
    -genkeypair \
    -keystore "$KEYSTORE" \
    -storepass android \
    -keypass android \
    -alias androiddebugkey \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname "CN=Android Debug,O=Prime Intellect,C=US" \
    >/dev/null
  cp "$KEYSTORE" "$KEYSTORE_CACHE"
fi

"$APKSIGNER" sign \
  --ks "$KEYSTORE" \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$BUILD_DIR/out/dummy-rl-app.apk" \
  "$BUILD_DIR/out/dummy-aligned.apk"

"$APKSIGNER" verify "$BUILD_DIR/out/dummy-rl-app.apk"

echo "$BUILD_DIR/out/dummy-rl-app.apk"
