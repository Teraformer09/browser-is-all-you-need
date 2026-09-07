#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${ADB_SERIAL:?Choose an explicit emulator serial; existing devices are not selected automatically}"
bash "$ROOT/scripts/build_apk.sh"
APK="$ROOT/app/shopping_android_app/app/build/outputs/apk/debug/app-debug.apk"
ADB=("${ADB_PATH:-adb}" -s "$ADB_SERIAL")
CART_BOOT_DEADLINE=$((SECONDS + 120))
while true; do
    CART_BOOT="$(timeout 10 "${ADB[@]}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
    if [[ "$CART_BOOT" == 1 ]] && timeout 10 "${ADB[@]}" shell pm path android 2>/dev/null | rg -q '^package:'; then break; fi
    if (( SECONDS >= CART_BOOT_DEADLINE )); then echo "Shopping emulator did not finish booting within 120 seconds" >&2; exit 2; fi
    sleep 2
done
"${ADB[@]}" install -r "$APK"
REMOTE="$("${ADB[@]}" shell pm path com.primeintellect.shoppingdemo | tr -d '\r' | sed -n 's/^package://p')"
[[ "$REMOTE" == /data/app/*/base.apk && "$REMOTE" != *$'\n'* ]] || exit 1
LOCAL_HASH="$(sha256sum "$APK" | cut -d' ' -f1)"
REMOTE_HASH="$("${ADB[@]}" shell sha256sum "$REMOTE" | cut -d' ' -f1)"
[[ "$LOCAL_HASH" == "$REMOTE_HASH" ]] || { echo "Installed APK hash mismatch" >&2; exit 1; }
printf 'Installed shopping demo SHA256=%s\n' "$LOCAL_HASH"
