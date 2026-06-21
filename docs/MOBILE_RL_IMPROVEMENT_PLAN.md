# Improvement Plan — prime-intellect-android-adk-rl-environments

This file now serves as both the original improvement-plan summary and a status tracker for what actually landed on `feature/mobile-rl-improvement-plan`.

## Scope

The requested work covered:

- parallel device/emulator pooling
- snapshot-based fast reset with fallback
- explicit fractional reward semantics
- standardized observation/action schema across ADB and AndroidWorld
- portability decisions for KVM-backed scaling
- verification that the Prime bridge is verifiers-native
- explicit AndroidWorld dependency pinning

## Status Summary

Implemented:

- device pool manager and pool-aware rollout / benchmark execution
- snapshot-aware reset manager with full-reset fallback
- explicit reward docs and shaped reward handling
- standardized `mobile_observation.v1` schema
- KVM-aware preflight and emulator-start validation
- explicit AndroidWorld commit pinning
- runtime hardening for real ADB execution:
  - configurable ADB command timeout
  - better `uiautomator dump` retries
  - blocking system-dialog dismissal
  - package-foreground checks before resource lookup
  - orchestrator config now respects environment overrides at runtime

Verified:

- unit tests
- integration tests
- AndroidWorld and Prime smoke tests already in the repo test suite
- real emulator preflight on `127.0.0.1:15555`
- real demo-APK proof benchmark run
- real demo-APK rollout run
- real scripted form-task execution on-device

Still open:

- live ride-booking scripted tasks are still failing in the current demo APK eval path
- multi-device `POOL_SIZE > 1` was implemented and unit-covered, but not hardware-validated in this session
- Prime eval and AndroidWorld full live runs were not re-run after the final ADB hardening changes

## Implementation Mapping

1. Device pool
   `android_adk_rl_env/device_pool.py`, `android_adk_rl_env/rollout_runner.py`, `android_adk_rl_env/proof_benchmark.py`, `scripts/mobile_rl.sh`, `Makefile`
2. Snapshot reset
   `android_adk_rl_env/reset_manager.py`, `android_adk_rl_env/adb_device.py`, `android_adk_rl_env/apk_env.py`, `android_adk_rl_env/android_world_bridge.py`
3. Reward granularity
   `android_adk_rl_env/tasks/dummy_apk.py`, `android_adk_rl_env/tasks/ride_booking.py`, `docs/REWARDS.md`
4. Observation/action schema
   `android_adk_rl_env/core/observations.py`, `docs/OBSERVATION_ACTION_SCHEMA.md`
5. Portability / KVM
   `scripts/mobile_preflight.sh`, `configs/mobile/orchestrator.env`, guide updates
6. Prime / verifiers audit
   confirmed in `prime_android_adk_rl_env/prime_android_adk_rl_env.py`
7. AndroidWorld pin
   `scripts/install_android_world.sh`, `configs/mobile/orchestrator.env`

## Chosen Portability Path

The repo now explicitly targets KVM-enabled cloud VMs or pods for real-emulator horizontal scaling. `/dev/kvm` is checked up front in preflight and emulator-start paths.

## Real Validation Notes

Live validation in this session used:

- serial: `127.0.0.1:15555`
- package: `com.primeintellect.dummyrl`
- reset mode: `full`

Observed live results:

- proof benchmark quick run: `exact_success_rate=0.5`
  - form tasks passed
  - ride tasks failed
- rollout run: `success_rate=0.5`
  - form tasks passed
  - ride tasks failed

Main runtime blockers fixed during validation:

- Android popup / crash dialogs interrupting the target app
- unstable `uiautomator dump` behavior
- ADB shell command timeouts that were too short for this emulator
- sourced orchestrator config overwriting caller-provided env vars like `RESET_MODE=full`

## Reference Docs

- [REWARDS.md](/data/Balram/prime-intellect-android-adk-rl-environments/docs/REWARDS.md)
- [OBSERVATION_ACTION_SCHEMA.md](/data/Balram/prime-intellect-android-adk-rl-environments/docs/OBSERVATION_ACTION_SCHEMA.md)
- [MOBILE_RL_IMPLEMENTATION_REPORT.md](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPLEMENTATION_REPORT.md)
