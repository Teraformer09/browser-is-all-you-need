#!/usr/bin/env bash
set -euo pipefail
APP="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$APP/build"
SDK="${ANDROID_SDK_ROOT:-/data/Balram/android-sdk}"
BT="$SDK/build-tools/34.0.0"
JAR="$SDK/platforms/android-34/android.jar"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$PATH"
export TMPDIR="$BUILD/tmp" TMP="$BUILD/tmp" TEMP="$BUILD/tmp"
export JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=$TMPDIR -Duser.home=$BUILD/java-home"
: "${ADB_SERVER_PORT:?Set the dedicated ADB server port}"
: "${ADB_SERIAL:?Set the dedicated emulator serial}"
WORK="$(mktemp -d "$BUILD/storage-tests.XXXXXX")"
cleanup() { case "$WORK" in "$BUILD"/storage-tests.*) rm -rf -- "$WORK";; esac; }
trap cleanup EXIT
mkdir -p "$WORK/classes" "$WORK/dex"
javac --release 8 -cp "$JAR:$BUILD/main-classes.jar" -d "$WORK/classes" "$APP/tests/StorageSmokeTest.java"
mapfile -t classes < <(find "$WORK/classes" -name '*.class')
"$BT/d8" --min-api 23 --lib "$JAR" --lib "$BUILD/main-classes.jar" --output "$WORK/dex" "${classes[@]}"
"$BT/aapt" package -f -M "$APP/tests/AndroidManifest.xml" -I "$JAR" -F "$WORK/tests.apk"
(cd "$WORK/dex" && zip -q "$WORK/tests.apk" classes.dex)
"$BT/zipalign" -f 4 "$WORK/tests.apk" "$WORK/aligned.apk"
"$BT/apksigner" sign --ks "$BUILD/debug.keystore" --ks-pass pass:android --key-pass pass:android --v4-signing-enabled false --out "$WORK/signed.apk" "$WORK/aligned.apk"
ADB=("$SDK/platform-tools/adb" -P "$ADB_SERVER_PORT" -s "$ADB_SERIAL")
"${ADB[@]}" install -r "$WORK/signed.apk"
"${ADB[@]}" shell am instrument -w com.primeintellect.amazonuidemo.uitests/com.primeintellect.amazonuidemo.StorageSmokeTest | tee "$WORK/result.log"
"${ADB[@]}" uninstall com.primeintellect.amazonuidemo.uitests
if ! rg -q "Storage smoke tests: [0-9]+ checks passed" "$WORK/result.log"; then
    echo "Storage instrumentation did not report a passing result" >&2
    exit 1
fi
