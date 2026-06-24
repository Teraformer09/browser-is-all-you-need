#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose.yaml}"
SERVICE="${SERVICE:-android-adk}"
CONTAINER_NAME="${CONTAINER_NAME:-androidworld-pipeline}"
ADB_SERIAL="${ADB_SERIAL:-emulator-5554}"
CONSOLE_PORT="${CONSOLE_PORT:-5554}"
GRPC_PORT="${GRPC_PORT:-8554}"
BENCH_OUTPUT_DIR="${BENCH_OUTPUT_DIR:-$ROOT_DIR/artifacts/benchmarks/uber30_androidworld}"
PRIME_OUTPUT_DIR="${PRIME_OUTPUT_DIR:-$ROOT_DIR/artifacts/prime_eval_androidworld}"
RESULT_MD="${RESULT_MD:-$ROOT_DIR/artifacts/androidworld_pipeline_results.md}"
MAX_RETRIES="${MAX_RETRIES:-3}"

cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "$COMPOSE_FILE")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f "$COMPOSE_FILE")
else
  echo "docker compose is required" >&2
  exit 1
fi

start_container() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  mkdir -p "$ROOT_DIR/artifacts/androidworld_bootstrap"
  "${COMPOSE[@]}" run -d --name "$CONTAINER_NAME" --service-ports "$SERVICE" bash -lc '
    set -euo pipefail
    cd /workspace
    mkdir -p artifacts/androidworld_bootstrap artifacts/docker_emulator
    if ! emulator -list-avds | grep -qx AndroidWorld_API_33; then
      echo "Creating Android AVD AndroidWorld_API_33"
      echo "no" | avdmanager create avd -n AndroidWorld_API_33 -k "system-images;android-33;google_apis;x86_64" --device "${ANDROID_WORLD_AVD_DEVICE:-pixel_6}"
    fi
    adb kill-server >/dev/null 2>&1 || true
    adb start-server >/dev/null 2>&1 || true
    emulator -avd AndroidWorld_API_33 -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -no-snapshot -grpc 8554 -ports 5554,5555 >/workspace/artifacts/androidworld_bootstrap/emulator.log 2>&1 &
    echo $! >/workspace/artifacts/androidworld_bootstrap/emulator.pid
    tail -f /dev/null
  '
}

wait_for_device() {
  local deadline=$((SECONDS + 600))
  while ((SECONDS < deadline)); do
    if docker exec "$CONTAINER_NAME" bash -lc 'adb kill-server >/dev/null 2>&1 || true; adb start-server >/dev/null 2>&1 || true; adb -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d "
" | grep -qx 1' >/dev/null 2>&1; then
      return 0
    fi
    sleep 10
  done
  return 1
}

run_benchmark() {
  mkdir -p "$BENCH_OUTPUT_DIR"
  docker exec     -e ADB_SERIAL="$ADB_SERIAL"     -e ADB_CMD_TIMEOUT_S=60     -e ANDROID_WORLD_GRPC_PORT="$GRPC_PORT"     -e ANDROID_WORLD_WAIT_TO_STABILIZE=1     -e RESET_MODE=full     -e POOL_SIZE=1     "$CONTAINER_NAME"     bash -lc 'cd /workspace && python3 -B -m android_adk_rl_env.proof_benchmark --backend android_world --tasks-dir tasks/uber_clone --attempts-per-instance 10 --pass-k 1 2 3 5 10 --output "$1"' bash "$BENCH_OUTPUT_DIR"
}

run_prime() {
  mkdir -p "$PRIME_OUTPUT_DIR"
  docker exec     -e ADB_SERIAL="$ADB_SERIAL"     -e PRIME_ANDROID_BACKEND=android_world     -e START_EMULATOR=0     -e STOP_EMULATOR_AFTER_RUN=0     -e OPENAI_API_KEY="${OPENAI_API_KEY:-}"     -e RESULTS_DIR="$PRIME_OUTPUT_DIR"     "$CONTAINER_NAME"     bash -lc 'cd /workspace && ./scripts/run_prime_eval_android_adk.sh'     >"$PRIME_OUTPUT_DIR/prime_eval.log" 2>&1
}

write_md() {
  local bench_summary="$BENCH_OUTPUT_DIR"/*/summary.json
  local prime_log="$PRIME_OUTPUT_DIR/prime_eval.log"
  {
    echo "# AndroidWorld + Prime Pipeline Results"
    echo
    echo "- Container: $CONTAINER_NAME"
    echo "- ADB serial: $ADB_SERIAL"
    echo "- Console port: $CONSOLE_PORT"
    echo "- GRPC port: $GRPC_PORT"
    echo "- Benchmark output: $BENCH_OUTPUT_DIR"
    echo "- Prime output: $PRIME_OUTPUT_DIR"
    echo
    echo "## Benchmark Summary"
    if [[ -f $bench_summary ]]; then
      python3 - "$bench_summary" <<'PYMD'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
summary = json.loads(path.read_text())
print(f"- run_id: {summary.get('run_id')}")
print(f"- backend: {summary.get('backend')}")
print(f"- tasks: {summary.get('task_count')}")
print(f"- total_attempts: {summary.get('total_attempts')}")
print(f"- exact_success_rate: {summary.get('exact_success_rate')}")
print(f"- avg_reward: {summary.get('avg_reward')}")
print(f"- pass@1: {summary.get('pass_at_k', {}).get('pass@1')}")
print(f"- pass@5: {summary.get('pass_at_k', {}).get('pass@5')}")
PYMD
    else
      echo "- missing summary.json"
    fi
    echo
    echo "## Prime Log"
    if [[ -f $prime_log ]]; then
      tail -n 40 "$prime_log"
    else
      echo "- missing prime log"
    fi
  } > "$RESULT_MD"
}

run_cycle() {
  local attempt=1
  while [[ "$attempt" -le "$MAX_RETRIES" ]]; do
    echo "Starting Docker AndroidWorld container attempt $attempt/$MAX_RETRIES"
    start_container
    if ! wait_for_device; then
      echo "AndroidWorld emulator did not become ready on attempt $attempt" >&2
      docker logs "$CONTAINER_NAME" >/tmp/androidworld_container_${attempt}.log 2>&1 || true
      attempt=$((attempt + 1))
      continue
    fi
    echo "Benchmarking AndroidWorld 30-task set"
    if run_benchmark; then
      echo "Running Prime eval"
      if run_prime; then
        write_md
        return 0
      fi
      echo "Prime eval failed on attempt $attempt" >&2
    else
      echo "AndroidWorld benchmark failed on attempt $attempt" >&2
    fi
    write_md
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    attempt=$((attempt + 1))
  done
  return 1
}

run_cycle
