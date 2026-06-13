#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/workspace"

"$ROOT_DIR/scripts/adb_wait_for_device.sh"
"$ROOT_DIR/scripts/build_dummy_apk.sh"
"$ROOT_DIR/scripts/install_dummy_apk.sh"

python3 -B -m android_adk_rl_env.train \
  --task dummy_apk \
  --policy openai \
  --backend adb \
  --episodes "${EPISODES:-1}" \
  --max-steps "${MAX_STEPS:-12}" \
  --model "${MODEL:-gpt-4o-mini}" \
  --output "${OUTPUT:-artifacts/rollouts/real_adb_openai_dummy_apk.jsonl}"
