#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/workspace}"
cd "$ROOT_DIR"

export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/android-sdk}"
export ANDROID_HOME="${ANDROID_HOME:-$ANDROID_SDK_ROOT}"
export ANDROID_BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$ANDROID_SDK_ROOT/build-tools/34.0.0}"
export ANDROID_WORLD_VENV="${ANDROID_WORLD_VENV:-/opt/android-adk-venv}"
export ANDROID_WORLD_SRC="${ANDROID_WORLD_SRC:-/opt/android_world}"
export ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$ROOT_DIR/.deps/android_avd}"
export ANDROID_WORLD_AVD_NAME="${ANDROID_WORLD_AVD_NAME:-AndroidWorld_API_33}"
export ANDROID_WORLD_SYSTEM_IMAGE="${ANDROID_WORLD_SYSTEM_IMAGE:-system-images;android-33;google_apis;x86_64}"
export ADB_PATH="${ADB_PATH:-$ANDROID_SDK_ROOT/platform-tools/adb}"
export EMULATOR_BIN="${EMULATOR_BIN:-$ANDROID_SDK_ROOT/emulator/emulator}"
export PATH="$ANDROID_WORLD_VENV/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

ensure_avd() {
  mkdir -p "$ANDROID_AVD_HOME"
  if ! "$EMULATOR_BIN" -list-avds | grep -qx "$ANDROID_WORLD_AVD_NAME"; then
    echo "Creating Android AVD $ANDROID_WORLD_AVD_NAME in $ANDROID_AVD_HOME"
    echo "no" | avdmanager create avd \
      -n "$ANDROID_WORLD_AVD_NAME" \
      -k "$ANDROID_WORLD_SYSTEM_IMAGE" \
      --device "${ANDROID_WORLD_AVD_DEVICE:-pixel_6}"
  fi
}

adb_cmd() {
  if [[ -n "${ADB_SERIAL:-}" ]]; then
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

EMULATOR_PID=""
start_emulator_if_needed() {
  if [[ "${START_EMULATOR:-0}" != "1" ]]; then
    return
  fi
  if [[ -z "${ADB_SERIAL:-}" ]]; then
    export ADB_SERIAL="emulator-${CONSOLE_PORT:-5556}"
  fi
  if adb_cmd get-state >/dev/null 2>&1; then
    wait_for_boot
    return
  fi
  ensure_avd
  warn_kvm
  local console_port="${CONSOLE_PORT:-5556}"
  local adb_port="${ADB_PORT:-$((console_port + 1))}"
  local grpc_port="${GRPC_PORT:-8554}"
  mkdir -p "$ROOT_DIR/artifacts/docker_emulator"
  "$EMULATOR_BIN" -avd "$ANDROID_WORLD_AVD_NAME" \
    -no-window \
    -no-audio \
    -no-boot-anim \
    -gpu swiftshader_indirect \
    -no-snapshot \
    -grpc "$grpc_port" \
    -ports "$console_port,$adb_port" \
    >"$ROOT_DIR/artifacts/docker_emulator/emulator.log" 2>&1 &
  EMULATOR_PID=$!
  echo "$EMULATOR_PID" > "$ROOT_DIR/artifacts/docker_emulator/emulator.pid"
  wait_for_boot
}

cleanup_emulator() {
  if [[ "${STOP_EMULATOR_AFTER_RUN:-0}" == "1" && -n "$EMULATOR_PID" ]]; then
    adb_cmd emu kill >/dev/null 2>&1 || true
  fi
}
trap cleanup_emulator EXIT

warn_kvm() {
  if [[ ! -e /dev/kvm ]]; then
    cat >&2 <<'MSG'
Warning: /dev/kvm is not visible inside the container.
Android emulator runs need a Linux host with KVM exposed, or they will be very slow/fail.
For local Docker/Prime runner use privileged mode, host IPC, and a large shm size.
MSG
  fi
}

show_help() {
  cat <<'HELP'
Prime Android ADK RL Docker commands:

  help                    Show this help.
  shell                   Open a bash shell in /workspace.
  tests                   Run unit tests.
  mock                    Run the dependency-free mock create_note task.
  build-apk               Build the dummy Android APK.
  adb-scripted            Build/install/run the real APK through ADB.
  android-world-status    Check whether AndroidWorld imports correctly.
  android-world-openai    Boot emulator, run AndroidWorld + OpenAI, save artifacts.
  prime-eval              Build/install/run Prime CLI verifiers eval.
  prime-start             Start SSH for Prime On-Demand custom Docker images.

Examples:
  docker compose run --rm android-adk tests
  docker compose run --rm android-adk mock
  OPENAI_API_KEY=... docker compose run --rm --service-ports android-adk android-world-openai
  OPENAI_API_KEY=... docker compose run --rm android-adk prime-eval

Any other command is executed directly.
HELP
}

cmd="${1:-help}"
case "$cmd" in
  help|-h|--help)
    show_help
    ;;
  shell|bash)
    exec bash
    ;;
  tests)
    exec python -m unittest discover -s tests
    ;;
  mock)
    exec python -m android_adk_rl_env.runner --task create_note --policy scripted
    ;;
  build-apk)
    exec "$ROOT_DIR/scripts/build_dummy_apk.sh"
    ;;
  adb-scripted)
    start_emulator_if_needed
    exec python -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk --compact
    ;;
  android-world-status)
    exec python -B -m android_adk_rl_env.android_world_runner --status
    ;;
  android-world-openai)
    warn_kvm
    ensure_avd
    exec "$ROOT_DIR/scripts/run_android_world_openai.sh"
    ;;
  prime-eval)
    warn_kvm
    if [[ "${START_EMULATOR:-0}" == "1" ]]; then
      ensure_avd
    fi
    exec "$ROOT_DIR/scripts/run_prime_eval_android_adk.sh"
    ;;
  prime-start)
    exec /usr/local/bin/prime-start.sh
    ;;
  *)
    exec "$@"
    ;;
esac
