#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIME_BIN="${PRIME_BIN:-prime}"
MODEL="${MODEL:-gpt-4o-mini}"
PROVIDER="${PROVIDER:-openai}"
BACKEND="${PRIME_ANDROID_BACKEND:-adb}"
ADB_PATH="${ADB_PATH:-adb}"
ADB_SERIAL="${ADB_SERIAL:-}"
MAX_TURNS="${MAX_TURNS:-15}"
RESULTS_DIR="${RESULTS_DIR:-$ROOT_DIR/artifacts/prime_eval_android_adk}"
SDK_ROOT="${ANDROID_SDK_ROOT:-/data/Balram/android-sdk}"
ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$ROOT_DIR/.deps/android_avd}"
AVD_NAME="${ANDROID_WORLD_AVD_NAME:-AndroidWorld_API_33}"
EMULATOR_BIN="${EMULATOR_BIN:-$SDK_ROOT/emulator/emulator}"
CONSOLE_PORT="${CONSOLE_PORT:-5556}"
ADB_PORT="${ADB_PORT:-$((CONSOLE_PORT + 1))}"
GRPC_PORT="${GRPC_PORT:-8554}"
START_EMULATOR="${START_EMULATOR:-0}"
STOP_EMULATOR_AFTER_RUN="${STOP_EMULATOR_AFTER_RUN:-0}"
EMULATOR_LOG="$RESULTS_DIR/emulator.log"
EMULATOR_PID=""
PYTHON_BIN="${PYTHON_BIN:-}"
export BACKEND ADB_PATH ADB_SERIAL MAX_TURNS
export ANDROID_SDK_ROOT="$SDK_ROOT" ANDROID_HOME="${ANDROID_HOME:-$SDK_ROOT}" ANDROID_AVD_HOME

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -n "${ANDROID_WORLD_VENV:-}" && -x "$ANDROID_WORLD_VENV/bin/python" ]]; then
    PYTHON_BIN="$ANDROID_WORLD_VENV/bin/python"
  elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

if [[ -z "$ADB_SERIAL" && "$START_EMULATOR" == "1" ]]; then
  ADB_SERIAL="emulator-$CONSOLE_PORT"
  export ADB_SERIAL
fi

adb_cmd() {
  if [[ -n "$ADB_SERIAL" ]]; then
    "$ADB_PATH" -s "$ADB_SERIAL" "$@"
  else
    "$ADB_PATH" "$@"
  fi
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
  echo "Timed out waiting for ${ADB_SERIAL:-default ADB device} to boot" >&2
  return 1
}

start_emulator_if_needed() {
  if [[ "$START_EMULATOR" != "1" ]]; then
    return
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
    -no-snapshot \
    -grpc "$GRPC_PORT" \
    -ports "$CONSOLE_PORT,$ADB_PORT" \
    >"$EMULATOR_LOG" 2>&1 &
  EMULATOR_PID=$!
  echo "$EMULATOR_PID" > "$RESULTS_DIR/emulator.pid"
  wait_for_boot
}

cleanup() {
  if [[ "$STOP_EMULATOR_AFTER_RUN" == "1" && -n "$EMULATOR_PID" ]]; then
    adb_cmd emu kill >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

mkdir -p "$RESULTS_DIR"
ENV_ARGS="$("$PYTHON_BIN" -c 'import json, os; print(json.dumps({"backend": os.environ["BACKEND"], "adb_path": os.environ["ADB_PATH"], "adb_serial": os.environ.get("ADB_SERIAL") or None, "max_turns": int(os.environ["MAX_TURNS"])}))')"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" && "$PROVIDER" == "openai" ]]; then
  echo "OPENAI_API_KEY missing. Put OPENAI_API_KEY=... in .env" >&2
  exit 1
fi

start_emulator_if_needed
"$ROOT_DIR/scripts/build_dummy_apk.sh" >/dev/null
ADB_PATH="$ADB_PATH" ADB_SERIAL="$ADB_SERIAL" "$ROOT_DIR/scripts/install_dummy_apk.sh" >/dev/null

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
"$PRIME_BIN" --plain eval run prime_android_adk_rl_env \
  --provider "$PROVIDER" \
  --model "$MODEL" \
  --api-key-var OPENAI_API_KEY \
  --api-base-url "${API_BASE_URL:-https://api.openai.com/v1}" \
  --api-client-type "${API_CLIENT_TYPE:-openai_chat_completions}" \
  --num-examples 1 \
  --rollouts-per-example 1 \
  --max-concurrent 1 \
  --max-tokens 256 \
  --temperature 0 \
  --env-args "$ENV_ARGS" \
  --state-columns android_final_reward,android_success,android_transitions,info \
  --save-results \
  --skip-upload \
  --disable-env-server \
  | tee "$RESULTS_DIR/prime_eval.log"
