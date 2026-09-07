#!/usr/bin/env bash
set -euo pipefail
[[ "${ALLOW_PAYMENT_UI_TEST:-0}" == 1 ]] || { echo "Set ALLOW_PAYMENT_UI_TEST=1 to authorize deterministic UI interaction." >&2; exit 2; }
: "${ADB_SERIAL:?Choose an explicit emulator serial}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/install_apk.sh"
JAVA_HOME="${JAVA_HOME:?}" bash "$ROOT/app/dummy_android_app/gradlew" --no-daemon -p "$ROOT/app/dummy_android_app" :app:assembleDebugAndroidTest
ADB=("${ADB_PATH:-adb}" -s "$ADB_SERIAL")
"${ADB[@]}" install -r "$ROOT/app/dummy_android_app/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
mkdir -p "$ROOT/artifacts"
RUN_DIR="$(mktemp -d "$ROOT/artifacts/ui_test.XXXXXX")"
"${ADB[@]}" shell am instrument -w com.primeintellect.paymentdemo.test/com.primeintellect.paymentdemo.PaymentUiTest | tee "$RUN_DIR/instrumentation.log"
grep -q 'PASS: 14 payment UI assertions' "$RUN_DIR/instrumentation.log"
printf 'UI_TEST_LOG=%s/instrumentation.log\n' "$RUN_DIR"
