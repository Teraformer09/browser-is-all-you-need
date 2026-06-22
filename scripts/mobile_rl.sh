#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT_DIR="$(pwd)"

CONFIG_FILE="${MOBILE_ORCHESTRATOR_CONFIG:-$ROOT_DIR/configs/mobile/orchestrator.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/mobile_rl.sh preflight|health
  ./scripts/mobile_rl.sh benchmark <proof|quick|release> [--attempts N|--attempts-per-instance N] [--max-steps N] [--pass-k "1 2 5 10"] [--bootstrap-samples N] [--pool-size N] [--collect-screenshot] [--json]
  ./scripts/mobile_rl.sh rollout [--json] [--no-openai] [--artifact-root DIR] [--pool-size N]
  ./scripts/mobile_rl.sh prime-eval [--backend adb|android_world] [--provider openai] [--model MODEL] [--max-turns N] [--start-emulator 0|1] [--stop-emulator-after-run 0|1]
  ./scripts/mobile_rl.sh android-world [--policy scripted|openai] [--episodes N] [--max-steps N] [--model MODEL] [--start-emulator 0|1] [--stop-emulator-after-run 0|1] [--artifact-dir DIR]
  ./scripts/mobile_rl.sh pipeline [--preset proof|quick|release] [--skip-benchmark] [--skip-rollout] [--skip-prime] [--skip-android-world]

Examples:
  ./scripts/mobile_rl.sh preflight
  ./scripts/mobile_rl.sh benchmark proof --collect-screenshot --json
  ./scripts/mobile_rl.sh rollout --json
  ./scripts/mobile_rl.sh prime-eval --backend adb --max-turns 12
  ./scripts/mobile_rl.sh android-world --policy scripted --episodes 1 --max-steps 15
  ./scripts/mobile_rl.sh pipeline --preset proof --skip-android-world
USAGE
}

require_mode_arg() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi
}

to_bool_int() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON)
      echo 1
      ;;
    0|false|FALSE|no|NO|off|OFF)
      echo 0
      ;;
    *)
      echo "${1:-0}"
      ;;
  esac
}

run_step() {
  echo
  echo "==> $*"
}

run_preflight() {
  POOL_SIZE="${POOL_SIZE:-1}" ./scripts/mobile_preflight.sh
}

resolve_pool_serials() {
  local requested="$1"
  local serials_raw="${ADB_SERIALS:-}"
  serials_raw="${serials_raw//,/ }"
  local serials=()
  local token
  for token in $serials_raw; do
    [[ -n "$token" ]] && serials+=("$token")
  done
  if [[ ${#serials[@]} -gt 0 ]]; then
    if [[ ${#serials[@]} -lt "$requested" ]]; then
      echo "ADB_SERIALS provides ${#serials[@]} devices, but pool size requested is $requested" >&2
      exit 1
    fi
    printf '%s\n' "${serials[@]:0:requested}"
    return
  fi

  if [[ "$requested" -gt 1 && -n "${ADB_SERIAL:-}" && "${ADB_SERIAL:-}" != emulator-* ]]; then
    echo "POOL_SIZE=$requested requires ADB_SERIALS or emulator-style ADB_SERIAL" >&2
    exit 1
  fi

  local start_port="${ADB_BASE_CONSOLE_PORT:-5554}"
  if [[ "${ADB_SERIAL:-}" == emulator-* ]]; then
    start_port="${ADB_SERIAL#emulator-}"
  fi

  if [[ "$requested" -eq 1 && -n "${ADB_SERIAL:-}" ]]; then
    printf '%s\n' "$ADB_SERIAL"
    return
  fi

  local i
  for ((i = 0; i < requested; i++)); do
    printf 'emulator-%d\n' "$((start_port + (i * 2)))"
  done
}

install_dummy_apk_for_pool() {
  local requested="$1"
  bash "$ROOT_DIR/scripts/build_dummy_apk.sh" >/dev/null
  while IFS= read -r serial; do
    [[ -z "$serial" ]] && continue
    ADB_SERIAL="$serial" bash "$ROOT_DIR/scripts/install_dummy_apk.sh" >/dev/null
  done < <(resolve_pool_serials "$requested")
}

run_benchmark() {
  local preset="$1"
  shift

  local attempts=""
  local max_steps=""
  local pass_k_raw="${BENCHMARK_PASS_K:-1 2 5 10}"
  local bootstrap_samples="${BENCHMARK_BOOTSTRAP_SAMPLES:-0}"
  local pool_size="${POOL_SIZE:-1}"
  local json=0
  local collect_screenshot=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --attempts|--attempts-per-instance)
        attempts="$2"
        shift 2
        ;;
      --max-steps)
        max_steps="$2"
        shift 2
        ;;
      --pass-k)
        pass_k_raw="$2"
        shift 2
        ;;
      --bootstrap-samples)
        bootstrap_samples="$2"
        shift 2
        ;;
      --pool-size)
        pool_size="$2"
        shift 2
        ;;
      --collect-screenshot|--screenshot)
        collect_screenshot=1
        shift
        ;;
      --json)
        json=1
        shift
        ;;
      *)
        echo "Unknown arg: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  local output_suffix=""
  case "$preset" in
    proof)
      output_suffix="proof"
      [[ -z "$attempts" ]] && attempts="${BENCHMARK_ATTEMPTS:-20}"
      ;;
    quick)
      output_suffix="proof-quick"
      [[ -z "$attempts" ]] && attempts="${BENCHMARK_ATTEMPTS_QUICK:-4}"
      ;;
    release)
      output_suffix="release"
      [[ -z "$attempts" ]] && attempts="${BENCHMARK_ATTEMPTS_RELEASE:-20}"
      ;;
    *)
      echo "Unknown benchmark preset: $preset" >&2
      usage
      exit 1
      ;;
  esac

  local max_steps_final="${max_steps:-${BENCHMARK_MAX_STEPS:-12}}"
  local output_dir="${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/$output_suffix"
  local pass_k
  read -r -a pass_k <<<"${pass_k_raw//,/ }"
  if [[ ${#pass_k[@]} -eq 0 ]]; then
    pass_k=(1 2 5 10)
  fi

  install_dummy_apk_for_pool "$pool_size"

  local run_output
  COLLECT_SCREENSHOT="$collect_screenshot" \
  SKIP_APK_INSTALL=1 \
  run_output="$($ROOT_DIR/scripts/run_proof_benchmark.sh \
    --backend "${ROLLOUT_BACKEND:-adb}" \
    --policy "${BENCHMARK_POLICY:-scripted}" \
    --attempts-per-instance "$attempts" \
    --max-steps "$max_steps_final" \
    --pass-k "${pass_k[@]}" \
    --bootstrap-samples "$bootstrap_samples" \
    --pool-size "$pool_size" \
    --output "$output_dir" \
    ${json:+--compact})"
  echo "$run_output"

  if [[ "$collect_screenshot" -eq 1 ]]; then
    local artifact_dir
    artifact_dir="$(printf '%s\n' "$run_output" | awk -F': ' '/^Artifacts:/ {print $2}' | tail -n 1)"
    if [[ -z "$artifact_dir" ]]; then
      artifact_dir="$output_dir"
    fi
    bash "$ROOT_DIR/scripts/collect_artifacts.sh" "$artifact_dir"
  fi
}

run_rollout() {
  local json=0
  local no_openai=0
  local artifact_root="${ROLLOUT_ARTIFACT_ROOT:-artifacts/runs}"
  local pool_size="${POOL_SIZE:-1}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json)
        json=1
        shift
        ;;
      --no-openai)
        no_openai=1
        shift
        ;;
      --artifact-root)
        artifact_root="$2"
        shift 2
        ;;
      --pool-size)
        pool_size="$2"
        shift 2
        ;;
      *)
        echo "Unknown arg: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  if [[ "$no_openai" -eq 0 && "$(to_bool_int "${ROLLOUT_WITH_OPENAI:-0}")" == "0" ]]; then
    no_openai=1
  fi

  install_dummy_apk_for_pool "$pool_size"

  local cmd
  cmd=(
    python3 -B -m android_adk_rl_env.rollout_runner
    --backend "${ROLLOUT_BACKEND:-adb}"
    --artifact-root "$artifact_root"
    --pool-size "$pool_size"
  )
  if [[ "$no_openai" -eq 1 ]]; then
    cmd+=(--no-openai)
  fi
  if [[ "$json" -eq 1 ]]; then
    cmd+=(--compact)
  fi
  "${cmd[@]}"
}

run_prime_eval() {
  local backend="${PRIME_ANDROID_BACKEND:-adb}"
  local provider="${PRIME_PROVIDER:-openai}"
  local model="${PRIME_MODEL:-gpt-4o-mini}"
  local max_turns="${PRIME_MAX_TURNS:-15}"
  local start_emulator="${PRIME_START_EMULATOR:-0}"
  local stop_emulator="${PRIME_STOP_EMULATOR_AFTER_RUN:-0}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --backend)
        backend="$2"
        shift 2
        ;;
      --provider)
        provider="$2"
        shift 2
        ;;
      --model)
        model="$2"
        shift 2
        ;;
      --max-turns)
        max_turns="$2"
        shift 2
        ;;
      --start-emulator)
        start_emulator="$2"
        shift 2
        ;;
      --stop-emulator-after-run)
        stop_emulator="$2"
        shift 2
        ;;
      *)
        echo "Unknown arg: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  PRIME_ANDROID_BACKEND="$backend" \
  PRIME_PROVIDER="$provider" \
  PRIME_MODEL="$model" \
  PRIME_MAX_TURNS="$max_turns" \
  PRIME_START_EMULATOR="$start_emulator" \
  PRIME_STOP_EMULATOR_AFTER_RUN="$stop_emulator" \
  "$ROOT_DIR/scripts/run_prime_eval_android_adk.sh"
}

run_android_world() {
  local policy="${ANDROID_WORLD_POLICY:-openai}"
  local episodes="${ANDROID_WORLD_EPISODES:-1}"
  local max_steps="${ANDROID_WORLD_MAX_STEPS:-15}"
  local model="${ANDROID_WORLD_MODEL:-gpt-4o-mini}"
  local start_emulator="${ANDROID_WORLD_START_EMULATOR:-1}"
  local stop_emulator="${ANDROID_WORLD_STOP_EMULATOR_AFTER_RUN:-0}"
  local artifact_dir="${ARTIFACT_DIR:-$ROOT_DIR/artifacts/android_world_openai_run}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --policy)
        policy="$2"
        shift 2
        ;;
      --episodes)
        episodes="$2"
        shift 2
        ;;
      --max-steps)
        max_steps="$2"
        shift 2
        ;;
      --model)
        model="$2"
        shift 2
        ;;
      --start-emulator)
        start_emulator="$2"
        shift 2
        ;;
      --stop-emulator-after-run)
        stop_emulator="$2"
        shift 2
        ;;
      --artifact-dir)
        artifact_dir="$2"
        shift 2
        ;;
      *)
        echo "Unknown arg: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  if [[ "$policy" != "scripted" && "$policy" != "openai" ]]; then
    echo "Unsupported AndroidWorld policy: $policy" >&2
    exit 1
  fi

  if [[ "$policy" == "scripted" && -z "${ARTIFACT_DIR:-}" ]]; then
    artifact_dir="$ROOT_DIR/artifacts/android_world_scripted_run"
  fi

  POLICY="$policy" \
  EPISODES="$episodes" \
  MAX_STEPS="$max_steps" \
  MODEL="$model" \
  START_EMULATOR="$start_emulator" \
  STOP_EMULATOR_AFTER_RUN="$stop_emulator" \
  ARTIFACT_DIR="$artifact_dir" \
  "$ROOT_DIR/scripts/run_android_world_openai.sh"
}

run_pipeline() {
  local run_benchmark_flag="${MOBILE_PIPELINE_BENCHMARK:-1}"
  local run_rollout_flag="${MOBILE_PIPELINE_ROLLOUT:-1}"
  local run_prime_flag="${MOBILE_PIPELINE_PRIME:-0}"
  local run_android_world_flag="${MOBILE_PIPELINE_ANDROID_WORLD:-0}"
  local preset="${MOBILE_PIPELINE_PRESET:-proof}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-benchmark)
        run_benchmark_flag=0
        shift
        ;;
      --skip-rollout)
        run_rollout_flag=0
        shift
        ;;
      --skip-prime)
        run_prime_flag=0
        shift
        ;;
      --skip-android-world)
        run_android_world_flag=0
        shift
        ;;
      --preset)
        preset="$2"
        shift 2
        ;;
      *)
        echo "Unknown arg: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  run_step "Health-check"
  run_preflight

  if [[ "$(to_bool_int "$run_benchmark_flag")" == "1" ]]; then
    run_step "Benchmark ($preset)"
    run_benchmark "$preset" --collect-screenshot
  fi

  if [[ "$(to_bool_int "$run_rollout_flag")" == "1" ]]; then
    run_step "Rollout"
    run_rollout
  fi

  if [[ "$(to_bool_int "$run_prime_flag")" == "1" ]]; then
    run_step "Prime eval"
    run_prime_eval
  fi

  if [[ "$(to_bool_int "$run_android_world_flag")" == "1" ]]; then
    run_step "AndroidWorld OpenAI"
    run_android_world
  fi

  echo "Pipeline completed."
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

MODE="$1"
shift

case "$MODE" in
  preflight)
    run_preflight
    ;;

  health)
    run_preflight
    ;;

  benchmark)
    require_mode_arg "$@"
    run_benchmark "$1" "${@:2}"
    ;;

  rollout)
    run_rollout "$@"
    ;;

  prime-eval|prime_eval)
    run_prime_eval "$@"
    ;;

  android-world)
    run_android_world "$@"
    ;;

  pipeline)
    run_pipeline "$@"
    ;;

  *)
    usage
    exit 1
    ;;
esac
