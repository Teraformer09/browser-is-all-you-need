# Prime Intellect Android ADK RL Environment

This repository is a real mobile Android RL and evaluation environment built around the demo APK `com.primeintellect.dummyrl`.

It now includes:

- real ADB-backed execution
- optional AndroidWorld-backed interaction
- pool-aware rollout and benchmark orchestration
- snapshot-aware reset management
- structured rollout and benchmark artifacts
- Prime / `verifiers` environment integration

## Current Status

The codebase is implemented and test-covered, and it was also revalidated on a real emulator in this session.

Live-validated on `2026-06-21`:

- preflight: passed
- proof benchmark quick run: passed
- rollout run: passed
- form tasks: working on real emulator
- ride tasks: still failing on the current live demo-APK path

Current real-run results:

- benchmark: `artifacts/benchmarks/proof-quick/20260621_171854`
  - `exact_success_rate=0.5`
- rollout: `artifacts/runs/20260621_172107`
  - `success_rate=0.5`

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
  device_pool.py             Pool-aware serial allocation
  reset_manager.py           Snapshot/full reset orchestration
  core/                      Actions, observations, reward, artifacts, safety, metrics
  policies/                  Scripted, OpenAI, random, local RL policy code
  tasks/                     Form and ride task definitions

dummy_android_app/           Android app source
prime_android_adk_rl_env/    Prime / verifiers environment
scripts/                     Build, install, run, AndroidWorld, Prime, Docker helpers
docs/                        Guides and implementation notes
tests/                       Unit, integration, AndroidWorld, and Prime tests
artifacts/                   Run outputs
```

## Fast Start

Use the orchestrator as the main entrypoint:

```bash
make mobile-help
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

Quick real benchmark:

```bash
ADB_SERIAL=127.0.0.1:15555 RESET_MODE=full ./scripts/mobile_rl.sh benchmark quick --attempts 1 --pool-size 1
```

Real rollout:

```bash
ADB_SERIAL=127.0.0.1:15555 RESET_MODE=full ./scripts/mobile_rl.sh rollout --pool-size 1 --no-openai --json
```

## What Is Working

- Unit and integration tests
- AndroidWorld and Prime smoke tests in the repo test suite
- Real demo-APK form interaction on emulator
- Real benchmark artifact generation
- Real rollout artifact generation
- pool-aware execution logic
- reset-mode switching with full-reset fallback

## Known Gap

The live ride-booking scripted flow still needs more work. That is why the current real benchmark and rollout runs score `2/4` rather than `4/4`.

## Main Docs

- [Improvement Plan](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPROVEMENT_PLAN.md)
- [Implementation Report](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPLEMENTATION_REPORT.md)
- [Reward Semantics](/data/Balram/prime-intellect-android-adk-rl-environments/docs/REWARDS.md)
- [Observation / Action Schema](/data/Balram/prime-intellect-android-adk-rl-environments/docs/OBSERVATION_ACTION_SCHEMA.md)
- [Complete Guide](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_COMPLETE_GUIDE.md)
