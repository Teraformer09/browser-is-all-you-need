# Prime Intellect Android ADK RL Environment

This repository is a real mobile Android RL and evaluation environment built around the demo APK `com.primeintellect.dummyrl`.

It now includes:

- real ADB-backed execution
- optional AndroidWorld-backed interaction
- spec-driven `mobile-rl` eval and benchmark CLI
- pool-aware rollout and benchmark orchestration
- snapshot-aware reset management
- strict `pass@k` and reward-reporting helpers
- structured rollout and benchmark artifacts
- Prime / `verifiers` environment integration

## Current Status

The codebase is implemented and test-covered, and the spec-driven CLI eval path was revalidated on a real emulator in this session.

Live-validated on `2026-06-22`:

- `mobile-rl health`: passed
- `mobile-rl eval --task tasks/form_default.yaml --policy scripted`: passed
- form task spec path: working on real emulator
- benchmark math and reward calibration: unit-tested
- ride specs: implemented, not revalidated live in this pass

Current real-run results:

- eval: structured JSON result with `harness_success=true` and `task_success=true`

The runtime loop is:

```text
Task
  -> Reset
  -> Observation
  -> Policy / model
  -> Structured action
  -> Device execution
  -> Durable APK state read
  -> Reward calculation
  -> Artifact write
```

## Repo Structure

```text
android_adk_rl_env/
  adb_device.py              Real device control and runtime hardening
  apk_env.py                 Step-based APK RL environment
  android_world_bridge.py    AndroidWorld-backed environment bridge
  rollout_runner.py          Multi-task rollout and artifact generation
  proof_benchmark.py         Repeatability / pass@k benchmark runner
  cli.py                     Unified mobile-rl CLI
  eval_runner.py             Shared spec-driven execution
  benchmarking/              pass@k and reward-reporting helpers
  device_pool.py             Pool-aware serial allocation
  reset_manager.py           Snapshot/full reset orchestration
  core/                      Actions, observations, reward, artifacts, safety, metrics
  policies/                  Scripted, OpenAI, random, local RL policy code
  tasks/                     Runnable task classes and registered checks

dummy_android_app/           Android app source
prime_android_adk_rl_env/    Prime / verifiers environment
scripts/                     Build, install, run, AndroidWorld, Prime, Docker helpers
docs/                        Guides and implementation notes
tests/                       Unit, integration, AndroidWorld, and Prime tests
artifacts/                   Run outputs
tasks/                       YAML task specs used by mobile-rl
```

## Fast Start

Use the CLI as the main entrypoint:

```bash
python3 -m android_adk_rl_env.cli --help
```

Recommended environment:

```bash
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_HOME=$ANDROID_SDK_ROOT
export ANDROID_AVD_HOME=/data/Balram/prime-intellect-android-adk-rl-environments/.deps/android_avd
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"
export ADB_SERIAL=127.0.0.1:15555
export RESET_MODE=full
export ADB_CMD_TIMEOUT_S=60
```

Preflight:

```bash
POOL_SIZE=1 MOBILE_REQUIRE_KVM=0 ./scripts/mobile_preflight.sh
```

Health check:

```bash
python3 -m android_adk_rl_env.cli health
```

Spec-driven real eval:

```bash
python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted
```

Spec-driven benchmark:

```bash
python3 -m android_adk_rl_env.cli benchmark --tasks-dir tasks --samples-per-task 10 --pass-k 1 2 3 5 10
```

## What Is Working

- Unit and integration tests
- AndroidWorld and Prime smoke tests in the repo test suite
- Real demo-APK form spec execution on emulator through `mobile-rl eval`
- Strict `pass@k` and reward-calibration test coverage
- Spec-driven benchmark artifacts through the new CLI path
- pool-aware execution logic
- reset-mode switching with full-reset fallback

## Known Gap

The ride-booking specs are implemented, but the live ride path was not revalidated in this pass. The currently confirmed real-device success path is the form spec through `mobile-rl eval`.

## Main Docs

- [Improvement Plan](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPROVEMENT_PLAN.md)
- [Implementation Report](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPLEMENTATION_REPORT.md)
- [CLI / Benchmark / Reward Upgrade](/data/Balram/prime-intellect-android-adk-rl-environments/docs/CLI_BENCHMARK_REWARD_UPGRADE.md)
- [Reward Semantics](/data/Balram/prime-intellect-android-adk-rl-environments/docs/REWARDS.md)
- [Observation / Action Schema](/data/Balram/prime-intellect-android-adk-rl-environments/docs/OBSERVATION_ACTION_SCHEMA.md)
- [Complete Guide](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_COMPLETE_GUIDE.md)
