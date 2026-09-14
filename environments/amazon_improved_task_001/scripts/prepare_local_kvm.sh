#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${ANDROID_SDK_ROOT:?Set the installed SDK directory (read-only)}"
: "${JAVA_HOME:?Set the installed Java 21 directory (read-only)}"
: "${CART_PYTHON:?Set the existing environment Python executable}"
: "${CART_FFMPEG:?Set the existing ffmpeg executable}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$TASK_ROOT${PYTHONPATH:+:$PYTHONPATH}"
# This is only a readiness check. No model key, Prime API, Docker or evaluation.
exec "$CART_PYTHON" -B -m amazon_improved_task_001.harness.local_runtime "$@"
