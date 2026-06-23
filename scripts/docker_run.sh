#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-prime-android-adk-rl-env:local}"
SERVICE="${SERVICE:-android-adk}"
COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml}"

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

cmd="${1:-help}"

case "$cmd" in
  build)
    "${COMPOSE[@]}" build "$SERVICE"
    ;;
  tests|test)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" tests "$@"
    ;;
  shell|bash)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" shell "$@"
    ;;
  build-apk)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" build-apk "$@"
    ;;
  adb-scripted)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" adb-scripted "$@"
    ;;
  android-world-openai)
    shift || true
    "${COMPOSE[@]}" run --rm --service-ports "$SERVICE" android-world-openai "$@"
    ;;
  prime-eval)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" prime-eval "$@"
    ;;
  health)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" ./scripts/mobile_rl.sh health "$@"
    ;;
  preflight)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" ./scripts/mobile_rl.sh preflight "$@"
    ;;
  rollout)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" ./scripts/mobile_rl.sh rollout "$@"
    ;;
  benchmark)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" ./scripts/mobile_rl.sh benchmark "$@"
    ;;
  *)
    "${COMPOSE[@]}" run --rm "$SERVICE" "$@"
    ;;
esac
