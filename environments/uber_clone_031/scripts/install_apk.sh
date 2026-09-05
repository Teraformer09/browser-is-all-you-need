#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"
adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then "$ADB_PATH" -s "$ADB_SERIAL" "$@"; else "$ADB_PATH" "$@"; fi
}
# Always run the source-aware cache check, even when an APK already exists.
APK_PATH="$(bash "$ROOT_DIR/scripts/build_apk.sh")"
adb_cmd wait-for-device
# Do not silently uninstall user app data if an unrelated signing key is present.
adb_cmd install -r "$APK_PATH"
INSTALLED_PATH="$(adb_cmd shell pm path com.primeintellect.dummyrl | tr -d '\r' | sed -n 's/^package://p')"
if [[ "$INSTALLED_PATH" != /data/app/*/base.apk || "$INSTALLED_PATH" == *$'\n'* ]]; then
  echo "Unexpected installed APK path: $INSTALLED_PATH" >&2; exit 1
fi
LOCAL_SHA="$(sha256sum "$APK_PATH" | cut -d' ' -f1)"
INSTALLED_SHA="$(adb_cmd shell sha256sum "$INSTALLED_PATH" | cut -d' ' -f1)"
[[ "$LOCAL_SHA" == "$INSTALLED_SHA" ]] || { echo "Installed APK hash mismatch" >&2; exit 1; }
printf 'Installed com.primeintellect.dummyrl SHA256=%s\n' "$INSTALLED_SHA"
