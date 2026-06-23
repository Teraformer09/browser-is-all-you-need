#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ANDROID_WORLD_VENV:-$ROOT_DIR/.venv}"
POLICY="${POLICY:-openai}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/artifacts/android_world_${POLICY}_run}"
EPISODES="${EPISODES:-1}"
MAX_STEPS="${MAX_STEPS:-15}"
MODEL="${MODEL:-gpt-4o-mini}"
SDK_ROOT="${ANDROID_SDK_ROOT:-/data/Balram/android-sdk}"
JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$ROOT_DIR/.deps/android_avd}"
AVD_NAME="${ANDROID_WORLD_AVD_NAME:-AndroidWorld_API_33}"
ADB_PATH="${ADB_PATH:-$SDK_ROOT/platform-tools/adb}"
CONSOLE_PORT="${CONSOLE_PORT:-}"
GRPC_PORT="${GRPC_PORT:-8554}"
ADB_SERIAL="${ADB_SERIAL:-}"
START_EMULATOR="${START_EMULATOR:-1}"
STOP_EMULATOR_AFTER_RUN="${STOP_EMULATOR_AFTER_RUN:-0}"
DEFAULT_ADB_SERIAL="${ANDROID_WORLD_DEFAULT_ADB_SERIAL:-127.0.0.1:15555}"
DEFAULT_CONSOLE_PORT="${ANDROID_WORLD_DEFAULT_CONSOLE_PORT:-15554}"
OUTPUT_JSONL="$ARTIFACT_DIR/rollout.jsonl"
VIDEO_DEVICE_PATH="/sdcard/android_world_openai_run.mp4"
SCREEN_DEVICE_PATH="/sdcard/android_world_openai_final.png"
SCREENRECORD_TIME_LIMIT="${SCREENRECORD_TIME_LIMIT:-180}"
SCREENRECORD_LOG="$ARTIFACT_DIR/screenrecord.log"
EMULATOR_BIN="${EMULATOR_BIN:-$SDK_ROOT/emulator/emulator}"
EMULATOR_LOG="$ARTIFACT_DIR/emulator.log"
REC_PID=""
EMULATOR_PID=""

export JAVA_HOME ANDROID_SDK_ROOT="$SDK_ROOT" ANDROID_HOME="$SDK_ROOT" ANDROID_AVD_HOME

mkdir -p "$ARTIFACT_DIR"
rm -f "$OUTPUT_JSONL" \
  "$ARTIFACT_DIR/result.json" \
  "$ARTIFACT_DIR/summary.json" \
  "$ARTIFACT_DIR/final_screen.png" \
  "$ARTIFACT_DIR/emulator_run.mp4" \
  "$SCREENRECORD_LOG"

if [[ ! -x "$VENV_DIR/bin/python" || ! -x "$EMULATOR_BIN" ]]; then
  "$ROOT_DIR/scripts/install_android_world.sh"
fi

if [[ ! -x "$ADB_PATH" ]]; then
  if command -v adb >/dev/null 2>&1; then
    ADB_PATH="$(command -v adb)"
  else
    echo "adb not found at $ADB_PATH" >&2
    exit 1
  fi
fi

adb_cmd() {
  "$ADB_PATH" -s "$ADB_SERIAL" "$@"
}

wait_for_boot() {
  "$ADB_PATH" start-server >/dev/null
  adb_cmd wait-for-device
  for _ in $(seq 1 180); do
    local booted
    booted="$(adb_cmd shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
    if [[ "$booted" == "1" ]]; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for $ADB_SERIAL to boot" >&2
  return 1
}

start_emulator_if_needed() {
  if [[ "$START_EMULATOR" != "1" ]]; then
    wait_for_boot
    return
  fi
  if [[ ! -e /dev/kvm ]]; then
    echo "/dev/kvm is required for emulator startup on the supported scaling path." >&2
    exit 1
  fi
  if adb_cmd get-state >/dev/null 2>&1; then
    wait_for_boot
    return
  fi
  if [[ ! -x "$EMULATOR_BIN" ]]; then
    echo "Android emulator binary missing: $EMULATOR_BIN" >&2
    exit 1
  fi
  "$EMULATOR_BIN" -avd "$AVD_NAME" \
    -no-window \
    -no-audio \
    -no-boot-anim \
    -gpu swiftshader_indirect \
    -no-snapshot-load \
    -grpc "$GRPC_PORT" \
    -ports "$CONSOLE_PORT,$ADB_PORT" \
    >"$EMULATOR_LOG" 2>&1 &
  EMULATOR_PID=$!
  echo "$EMULATOR_PID" > "$ARTIFACT_DIR/emulator.pid"
  wait_for_boot
}

stop_recording() {
  if [[ -n "$REC_PID" ]]; then
    adb_cmd shell pkill -INT screenrecord >/dev/null 2>&1 || true
    sleep 1
    adb_cmd shell pkill screenrecord >/dev/null 2>&1 || true
    wait "$REC_PID" >/dev/null 2>&1 || true
    REC_PID=""
  fi
}

cleanup() {
  stop_recording
  if [[ "$STOP_EMULATOR_AFTER_RUN" == "1" && -n "$EMULATOR_PID" ]]; then
    adb_cmd emu kill >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

resolve_live_adb_serial() {
  if [[ -n "$ADB_SERIAL" ]]; then
    return
  fi
  local serial
  serial="$($ADB_PATH devices 2>/dev/null | awk -v preferred="$DEFAULT_ADB_SERIAL" '
    $2=="device" && $1==preferred { print $1; exit }
    $2=="device" && $1 !~ /^List/ && !seen { seen=$1 }
    END { if (seen) print seen }
  ')"
  if [[ -n "$serial" ]]; then
    ADB_SERIAL="$serial"
    return
  fi
  if [[ "$START_EMULATOR" == "1" ]]; then
    ADB_SERIAL="$DEFAULT_ADB_SERIAL"
    return
  fi
  echo "No live adb device found and ADB_SERIAL was not provided." >&2
  exit 1
}

resolve_console_port() {
  if [[ -n "$CONSOLE_PORT" ]]; then
    return
  fi
  if [[ "$ADB_SERIAL" =~ ^emulator-([0-9]+)$ ]]; then
    CONSOLE_PORT="${BASH_REMATCH[1]}"
    return
  fi
  if [[ "$ADB_SERIAL" =~ :([0-9]+)$ ]]; then
    CONSOLE_PORT="$((BASH_REMATCH[1] - 1))"
    return
  fi
  CONSOLE_PORT="$DEFAULT_CONSOLE_PORT"
}

resolve_live_adb_serial
resolve_console_port
ADB_PORT="$((CONSOLE_PORT + 1))"

if [[ "$POLICY" == "openai" ]]; then
  "$VENV_DIR/bin/python" - <<'CHECKKEY'
from android_adk_rl_env.config import get_openai_api_key
if not get_openai_api_key():
    raise SystemExit('OPENAI_API_KEY missing. Put OPENAI_API_KEY=... in .env')
print('OPENAI_API_KEY loaded')
CHECKKEY
fi

start_emulator_if_needed

"$ROOT_DIR/scripts/build_dummy_apk.sh" >/dev/null
ADB_PATH="$ADB_PATH" ADB_SERIAL="$ADB_SERIAL" "$ROOT_DIR/scripts/install_dummy_apk.sh" >/dev/null

adb_cmd shell rm -f "$VIDEO_DEVICE_PATH" "$SCREEN_DEVICE_PATH" >/dev/null 2>&1 || true
adb_cmd shell screenrecord --time-limit "$SCREENRECORD_TIME_LIMIT" "$VIDEO_DEVICE_PATH" >"$SCREENRECORD_LOG" 2>&1 &
REC_PID=$!

set +e
"$VENV_DIR/bin/python" -B -m android_adk_rl_env.android_world_runner \
  --backend android_world \
  --policy "$POLICY" \
  --model "$MODEL" \
  --episodes "$EPISODES" \
  --max-steps "$MAX_STEPS" \
  --output "$OUTPUT_JSONL" \
  --adb-path "$ADB_PATH" \
  --adb-serial "$ADB_SERIAL" \
  --console-port "$CONSOLE_PORT" \
  --grpc-port "$GRPC_PORT" \
  --compact | tee "$ARTIFACT_DIR/result.json"
RUN_STATUS=${PIPESTATUS[0]}
set -e

stop_recording
trap - EXIT

adb_cmd shell screencap -p "$SCREEN_DEVICE_PATH" >/dev/null 2>&1 || true
adb_cmd pull "$VIDEO_DEVICE_PATH" "$ARTIFACT_DIR/emulator_run.mp4" >/dev/null 2>&1 || true
adb_cmd pull "$SCREEN_DEVICE_PATH" "$ARTIFACT_DIR/final_screen.png" >/dev/null 2>&1 || true

"$VENV_DIR/bin/python" - "$ARTIFACT_DIR" "$OUTPUT_JSONL" "$RUN_STATUS" "$ADB_SERIAL" "$CONSOLE_PORT" "$GRPC_PORT" "$MODEL" "$POLICY" <<'SUMMARYPY'
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
rollout_path = Path(sys.argv[2])
run_status = int(sys.argv[3])
summary = {
    'run_status': run_status,
    'rollout_jsonl': str(rollout_path),
    'adb_serial': sys.argv[4],
    'console_port': int(sys.argv[5]),
    'grpc_port': int(sys.argv[6]),
    'model': sys.argv[7],
    'policy': sys.argv[8],
}
result_path = root / 'result.json'
if result_path.exists():
    text = result_path.read_text().strip()
    if text:
        try:
            summary['result'] = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError:
            summary['raw_result'] = text[-4000:]
if rollout_path.exists():
    rows = [json.loads(line) for line in rollout_path.read_text().splitlines() if line.strip()]
    summary['rollout_count'] = len(rows)
    if rows:
        last = rows[-1]
        summary['last_rollout'] = {
            'success': last.get('success'),
            'reward': last.get('reward'),
            'final_reward': last.get('final_reward'),
            'steps': last.get('steps'),
        }
summary['artifacts'] = {
    'result': str(root / 'result.json'),
    'rollout': str(rollout_path),
    'video': str(root / 'emulator_run.mp4'),
    'screenshot': str(root / 'final_screen.png'),
    'emulator_log': str(root / 'emulator.log'),
    'screenrecord_log': str(root / 'screenrecord.log'),
    'summary': str(root / 'summary.json'),
}
(root / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True))
print(json.dumps(summary, sort_keys=True))
SUMMARYPY

cleanup
exit "$RUN_STATUS"
