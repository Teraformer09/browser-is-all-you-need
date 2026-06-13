#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-prime-android-adk-rl-env:local}"
NAME="${NAME:-pi-docker-runner}"
SSH_PORT="${SSH_PORT:-2222}"
CONSOLE_PORT="${CONSOLE_PORT:-5556}"
GRPC_PORT="${GRPC_PORT:-8554}"

cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/.deps/android_avd" "$ROOT_DIR/artifacts"

if [[ "${BUILD_IMAGE:-0}" == "1" ]]; then
  docker build --platform linux/amd64 -t "$IMAGE" .
fi

docker rm -f "$NAME" >/dev/null 2>&1 || true

command_args=("$@")
if [[ ${#command_args[@]} -eq 0 ]]; then
  command_args=(prime-start)
fi

docker run --rm \
  --name "$NAME" \
  --privileged \
  --ipc=host \
  --shm-size=8G \
  -p "$SSH_PORT:22" \
  -p "$CONSOLE_PORT-$((CONSOLE_PORT + 1)):$CONSOLE_PORT-$((CONSOLE_PORT + 1))" \
  -p "$GRPC_PORT:$GRPC_PORT" \
  -e PUBLIC_KEY="${PUBLIC_KEY:-}" \
  -e SSH_PORT=22 \
  -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  -e PRIME_API_KEY="${PRIME_API_KEY:-}" \
  -e PRIME_ANDROID_BACKEND="${PRIME_ANDROID_BACKEND:-adb}" \
  -e API_BASE_URL="${API_BASE_URL:-https://api.openai.com/v1}" \
  -e API_CLIENT_TYPE="${API_CLIENT_TYPE:-openai_chat_completions}" \
  -e MODEL="${MODEL:-gpt-4o-mini}" \
  -e CONSOLE_PORT="$CONSOLE_PORT" \
  -e ADB_SERIAL="${ADB_SERIAL:-emulator-$CONSOLE_PORT}" \
  -e GRPC_PORT="$GRPC_PORT" \
  -e STOP_EMULATOR_AFTER_RUN="${STOP_EMULATOR_AFTER_RUN:-1}" \
  -v "$ROOT_DIR:/workspace" \
  -v "$ROOT_DIR/.deps/android_avd:/workspace/.deps/android_avd" \
  -v "$ROOT_DIR/artifacts:/workspace/artifacts" \
  "$IMAGE" \
  "${command_args[@]}"
