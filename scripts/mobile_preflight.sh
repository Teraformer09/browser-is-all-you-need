#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POOL_SIZE="${POOL_SIZE:-1}"
ADB_SERIAL="${ADB_SERIAL:-}"
ADB_SERIALS="${ADB_SERIALS:-}"
ADB_BASE_CONSOLE_PORT="${ADB_BASE_CONSOLE_PORT:-5554}"
MOBILE_REQUIRE_KVM="${MOBILE_REQUIRE_KVM:-1}"

resolve_pool_serials() {
  local requested="$1"
  local serials_raw="${ADB_SERIALS//,/ }"
  local serials=()
  local token

  for token in $serials_raw; do
    [[ -n "$token" ]] && serials+=("$token")
  done

  if [[ ${#serials[@]} -gt 0 ]]; then
    if [[ ${#serials[@]} -lt "$requested" ]]; then
      echo "ADB_SERIALS provides ${#serials[@]} devices, but POOL_SIZE=$requested" >&2
      exit 1
    fi
    printf '%s\n' "${serials[@]:0:requested}"
    return
  fi

  if [[ "$requested" -gt 1 && -n "$ADB_SERIAL" && "$ADB_SERIAL" != emulator-* ]]; then
    echo "POOL_SIZE=$requested requires ADB_SERIALS or emulator-style ADB_SERIAL" >&2
    exit 1
  fi

  local start_port="$ADB_BASE_CONSOLE_PORT"
  if [[ "$ADB_SERIAL" == emulator-* ]]; then
    start_port="${ADB_SERIAL#emulator-}"
  fi

  if [[ "$requested" -eq 1 && -n "$ADB_SERIAL" ]]; then
    printf '%s\n' "$ADB_SERIAL"
    return
  fi

  local i
  for ((i = 0; i < requested; i++)); do
    printf 'emulator-%d\n' "$((start_port + (i * 2)))"
  done
}

if [[ "$MOBILE_REQUIRE_KVM" == "1" && ! -e /dev/kvm ]]; then
  echo "KVM preflight failed: /dev/kvm is not available. This repo's scaled emulator path targets KVM-enabled hosts." >&2
  exit 1
fi

echo "pool_size=$POOL_SIZE"
while IFS= read -r serial; do
  [[ -z "$serial" ]] && continue
  echo "-- checking $serial"
  ADB_SERIAL="$serial" "$ROOT_DIR/scripts/adb_healthcheck.sh"
done < <(resolve_pool_serials "$POOL_SIZE")
