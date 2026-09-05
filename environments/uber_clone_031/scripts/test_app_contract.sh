#!/usr/bin/env bash
# Instrumentation exercises app listeners directly, including hidden-button clicks.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/android-sdk}"
TOOLS="${ANDROID_BUILD_TOOLS:-$SDK_ROOT/build-tools/35.0.0}"
ADB="${ADB_PATH:-$SDK_ROOT/platform-tools/adb}"
SERIAL="${ADB_SERIAL:-emulator-5556}"
TEST_OUT="${TEST_OUTPUT_DIR:-$ROOT_DIR/artifacts/app_contract}"
KEYSTORE="${TEST_KEYSTORE:-$ROOT_DIR/app/dummy_android_app/debug.keystore}"
mkdir -p "$TEST_OUT/classes" "$TEST_OUT/dex"
javac -source 8 -target 8 -bootclasspath "$SDK_ROOT/platforms/android-34/android.jar" \
  -d "$TEST_OUT/classes" "$ROOT_DIR/tests/android/ContractInstrumentation.java"
"$TOOLS/d8" --min-api 23 --lib "$SDK_ROOT/platforms/android-34/android.jar" \
  --output "$TEST_OUT/dex" "$TEST_OUT"/classes/com/primeintellect/dummyrl/contracttest/*.class
"$TOOLS/aapt" package -f -M "$ROOT_DIR/tests/android/AndroidManifest.xml" \
  -I "$SDK_ROOT/platforms/android-34/android.jar" -F "$TEST_OUT/test-unsigned.apk"
(cd "$TEST_OUT/dex" && zip -q "$TEST_OUT/test-unsigned.apk" classes.dex)
"$TOOLS/zipalign" -f -p 4 "$TEST_OUT/test-unsigned.apk" "$TEST_OUT/test-aligned.apk"
"$TOOLS/apksigner" sign --ks "$KEYSTORE" --ks-pass pass:android --key-pass pass:android \
  --out "$TEST_OUT/contract-test.apk" "$TEST_OUT/test-aligned.apk"
"$ADB" -s "$SERIAL" install -r "$TEST_OUT/contract-test.apk"
"$ADB" -s "$SERIAL" shell am force-stop com.primeintellect.dummyrl
"$ADB" -s "$SERIAL" shell am instrument -w \
  com.primeintellect.dummyrl.contracttest/.ContractInstrumentation | tee "$TEST_OUT/result.log"
grep -q "PASS: 29 app-side contract assertions" "$TEST_OUT/result.log"
