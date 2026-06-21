#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECT_SCREENSHOT="${COLLECT_SCREENSHOT:-0}"
RUNNER_TIMEOUT_S="${PROOF_DEVICE_TIMEOUT_S:-90}"
SKIP_APK_INSTALL="${SKIP_APK_INSTALL:-0}"

ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"

if [[ "$RUNNER_TIMEOUT_S" -le 0 ]]; then
  RUNNER_TIMEOUT_S=30
fi

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
}

check_adb_device() {
  if ! command -v "$ADB_PATH" >/dev/null 2>&1; then
    echo "adb not found. Set ADB_PATH to a valid adb binary." >&2
    return 1
  fi

  "$ADB_PATH" start-server >/dev/null

  if [[ -n "$ADB_SERIAL" && "$ADB_SERIAL" == *:* ]]; then
    "$ADB_PATH" connect "$ADB_SERIAL" >/dev/null 2>&1 || true
  fi

  deadline=$((SECONDS + RUNNER_TIMEOUT_S))
  while ((SECONDS < deadline)); do
    if [[ -n "$ADB_SERIAL" ]]; then
      state="$(adb_cmd get-state 2>/dev/null | tr -d '\r' | tr -d '\n' || true)"
      if [[ "$state" == "device" ]]; then
        break
      fi
    else
      if adb_cmd devices 2>/dev/null | awk 'NR>1 && $2=="device" { found=1; exit } END { exit 1-found }'; then
        break
      fi
    fi
    sleep 1
  done

  if [[ "$SECONDS" -ge "$deadline" ]]; then
    echo "Timed out waiting for Android device availability ($RUNNER_TIMEOUT_S s)" >&2
    return 1
  fi

  if adb_cmd shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' | tr -d '\n' | grep -qx "1"; then
    return 0
  fi

  deadline=$((SECONDS + RUNNER_TIMEOUT_S))
  while ((SECONDS < deadline)); do
    booted="$(adb_cmd shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' | tr -d '\n' || true)"
    if [[ "$booted" == "1" ]]; then
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for Android boot completion ($RUNNER_TIMEOUT_S s)" >&2
  return 1
}

cd "$ROOT_DIR"

check_adb_device

if [[ "$SKIP_APK_INSTALL" != "1" ]]; then
  bash "$ROOT_DIR/scripts/build_dummy_apk.sh" >/dev/null
  bash "$ROOT_DIR/scripts/install_dummy_apk.sh" >/dev/null
fi

RUN_OUTPUT="$(python3 -B -m android_adk_rl_env.proof_benchmark "$@")"
echo "$RUN_OUTPUT"

if [[ "$COLLECT_SCREENSHOT" == "1" ]]; then
  ARTIFACT_DIR="$(echo "$RUN_OUTPUT" | awk -F': ' '/^Artifacts: /{print $2}' | tail -n 1)"
  if [[ -n "${ARTIFACT_DIR}" && -d "${ARTIFACT_DIR}" ]]; then
    bash "$ROOT_DIR/scripts/collect_artifacts.sh" "$ARTIFACT_DIR"
  fi
fi
