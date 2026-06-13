#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-prime-android-adk-rl-env:local}"
SERVICE="${SERVICE:-android-adk}"

cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "docker compose is required" >&2
  exit 1
fi

cmd="${1:-help}"

case "$cmd" in
  build)
    "${COMPOSE[@]}" build "$SERVICE"
    ;;
  android-world-openai)
    shift || true
    "${COMPOSE[@]}" run --rm --service-ports "$SERVICE" android-world-openai "$@"
    ;;
  shell|bash)
    shift || true
    "${COMPOSE[@]}" run --rm "$SERVICE" shell "$@"
    ;;
  *)
    "${COMPOSE[@]}" run --rm "$SERVICE" "$@"
    ;;
esac
