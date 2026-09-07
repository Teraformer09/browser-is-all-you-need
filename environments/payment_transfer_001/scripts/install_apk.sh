#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${ADB_SERIAL:?Choose an explicit emulator serial; existing devices are not selected automatically}"
bash "$ROOT/scripts/build_apk.sh"
APK="$ROOT/app/dummy_android_app/app/build/outputs/apk/debug/app-debug.apk"
ADB=("${ADB_PATH:-adb}" -s "$ADB_SERIAL")
"${ADB[@]}" install -r "$APK"
REMOTE="$("${ADB[@]}" shell pm path com.primeintellect.paymentdemo | tr -d '\r' | sed -n 's/^package://p')"
[[ "$REMOTE" == /data/app/*/base.apk && "$REMOTE" != *$'\n'* ]] || exit 1
LOCAL_HASH="$(sha256sum "$APK" | cut -d' ' -f1)"
REMOTE_HASH="$("${ADB[@]}" shell sha256sum "$REMOTE" | cut -d' ' -f1)"
[[ "$LOCAL_HASH" == "$REMOTE_HASH" ]] || { echo "Installed APK hash mismatch" >&2; exit 1; }
printf 'Installed payment demo SHA256=%s\n' "$LOCAL_HASH"
