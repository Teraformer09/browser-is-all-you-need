# Mobile RL Implementation Report

Branch: `feature/mobile-rl-improvement-plan`

## What was implemented

- Added pool-aware device allocation in `android_adk_rl_env/device_pool.py`.
- Added concurrent execution for rollout and proof benchmark paths, wired through `scripts/mobile_rl.sh` and `Makefile`.
- Added snapshot-aware reset orchestration in `android_adk_rl_env/reset_manager.py` with full-reset fallback.
- Added emulator snapshot helpers and runtime hardening in `android_adk_rl_env/adb_device.py`.
- Standardized observations to `mobile_observation.v1` across ADB and AndroidWorld.
- Made scripted form and ride tasks emit fractional shaped rewards while preserving binary `final_reward`.
- Added KVM-aware preflight in `scripts/mobile_preflight.sh`.
- Pinned AndroidWorld install flow to commit `d9c569f764b3a5629321858de03ff653d0f24056`.
- Fixed orchestrator config loading so runtime env overrides now win over file defaults.

## Architecture Notes

- Single-device behavior is preserved with `POOL_SIZE=1`.
- Parallel execution uses a lease-based pool instead of scattering serial-selection logic through runners.
- Reset behavior is centralized in `reset_manager.py`, so ADB env, AndroidWorld env, and scripted tasks all use the same reset policy.
- Prime bridge audit: `prime_android_adk_rl_env/prime_android_adk_rl_env.py` is already a real `verifiers` `MultiTurnEnv`, so no shim refactor was required.
- Real-device runtime stability now depends less on ideal emulator behavior because the ADB layer dismisses common blocking dialogs and tolerates flaky `uiautomator` output better.

## New Operator-Facing Controls

- `POOL_SIZE`
- `RESET_MODE=snapshot|full`
- `ADB_SERIALS`
- `ADB_BASELINE_SNAPSHOT`
- `MOBILE_REQUIRE_KVM`
- vendored `third_party/android_world` copy at commit `d9c569f764b3a5629321858de03ff653d0f24056`
- `ADB_CMD_TIMEOUT_S`

## Verification Coverage Added

- device pool expansion
- snapshot baseline creation
- snapshot restore fallback
- observation schema presence
- fractional ride reward behavior

## Live Validation Completed

Code-level verification:

- `python3 -m unittest discover -s tests/unit`
- `python3 -m unittest discover -s tests/integration`
- `python3 -m unittest discover -s tests/android_world`
- `python3 -m unittest discover -s tests/prime`
- targeted re-runs after runtime fixes
- `py_compile` on changed runtime modules

Real emulator verification in this session:

- serial: `127.0.0.1:15555`
- package installed and preflight passed
- scripted form flow manually executed successfully on-device
- proof benchmark quick run completed:
  - artifact: `artifacts/benchmarks/proof-quick/20260621_171854`
  - result: `exact_success_rate=0.5`
- rollout run completed:
  - artifact: `artifacts/runs/20260621_172107`
  - result: `success_rate=0.5`

## Current Known Gap

The form-task path is live-validated and working. The ride-booking scripted tasks still fail in the current real demo-APK evaluation path, so the real benchmark / rollout results are currently `2/4` rather than `4/4`.
