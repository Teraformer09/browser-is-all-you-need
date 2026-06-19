#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/mobile_rl.sh preflight
  ./scripts/mobile_rl.sh health
  ./scripts/mobile_rl.sh benchmark <proof|quick|release> [--json] [--attempts N] [--max-steps N] [--collect-screenshot]
  ./scripts/mobile_rl.sh rollout [--json]

Examples:
  ./scripts/mobile_rl.sh preflight
  ./scripts/mobile_rl.sh benchmark quick --attempts 4 --json
  ./scripts/mobile_rl.sh benchmark proof --collect-screenshot
  ./scripts/mobile_rl.sh rollout
USAGE
}

require_mode_arg() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 1
  fi
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

MODE="$1"
shift

case "$MODE" in
  preflight)
    ./scripts/adb_healthcheck.sh "$@"
    ;;

  health)
    ./scripts/adb_healthcheck.sh "$@"
    ;;

  benchmark)
    require_mode_arg "$@"
    PRESET="$1"
    shift

    JSON=0
    ATTEMPTS=""
    MAX_STEPS=""
    COLLECT_SCREENSHOT=0

    while [[ $# -gt 0 ]]; do
      case "$1" in
        --json)
          JSON=1
          shift
          ;;
        --attempts)
          ATTEMPTS="$2"
          shift 2
          ;;
        --max-steps)
          MAX_STEPS="$2"
          shift 2
          ;;
        --collect-screenshot)
          COLLECT_SCREENSHOT=1
          shift
          ;;
        *)
          echo "Unknown arg: $1" >&2
          usage
          exit 1
          ;;
      esac
    done

    case "$PRESET" in
      proof)
        TARGET="benchmark-proof"
        ;;
      quick)
        TARGET="benchmark-quick"
        ;;
      release)
        TARGET="benchmark-release"
        ;;
      *)
        echo "Unknown benchmark preset: $PRESET" >&2
        usage
        exit 1
        ;;
    esac

    ENV_CMD=(
      PROOF_DEVICE_TIMEOUT_S="${PROOF_DEVICE_TIMEOUT_S:-90}"
    )

    if [[ -n "$ATTEMPTS" ]]; then
      if [[ "$PRESET" == "proof" ]]; then
        ENV_CMD+=("BENCHMARK_ATTEMPTS=$ATTEMPTS")
      elif [[ "$PRESET" == "quick" ]]; then
        ENV_CMD+=("BENCHMARK_ATTEMPTS_QUICK=$ATTEMPTS")
      else
        ENV_CMD+=("BENCHMARK_ATTEMPTS_RELEASE=$ATTEMPTS")
      fi
    fi

    if [[ -n "$MAX_STEPS" ]]; then
      ENV_CMD+=("BENCHMARK_MAX_STEPS=$MAX_STEPS")
    fi

    if [[ "$COLLECT_SCREENSHOT" -eq 1 ]]; then
      ENV_CMD+=("COLLECT_SCREENSHOT=1")
    fi

    if [[ "$JSON" -eq 1 ]]; then
      # keep output parse-friendly for wrappers that expect JSON style logs
      ENV_CMD+=("W8RL_COMPACT=1")
      echo "Running benchmark in compact mode"
    fi

    if [[ ${#ENV_CMD[@]} -gt 0 ]]; then
      "${ENV_CMD[@]}" make "$TARGET"
    else
      make "$TARGET"
    fi
    ;;

  rollout)
    JSON=0
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --json)
          JSON=1
          shift
          ;;
        *)
          echo "Unknown arg: $1" >&2
          usage
          exit 1
          ;;
      esac
    done

    if [[ "$JSON" -eq 1 ]]; then
      ADB_SERIAL="${ADB_SERIAL:-}" ROLLOUT_BACKEND=adb python3 -B -m android_adk_rl_env.rollout_runner --backend adb --compact
    else
      ./scripts/run_rollout.sh
    fi
    ;;

  *)
    usage
    exit 1
    ;;
esac
