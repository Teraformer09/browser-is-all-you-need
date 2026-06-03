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
export BACKEND ADB_PATH ADB_SERIAL MAX_TURNS

mkdir -p "$RESULTS_DIR"
ENV_ARGS="$($ROOT_DIR/.venv/bin/python -c 'import json, os; print(json.dumps({"backend": os.environ["BACKEND"], "adb_path": os.environ["ADB_PATH"], "adb_serial": os.environ.get("ADB_SERIAL") or None, "max_turns": int(os.environ["MAX_TURNS"])}))')"

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
  --debug \
  | tee "$RESULTS_DIR/prime_eval.log"
