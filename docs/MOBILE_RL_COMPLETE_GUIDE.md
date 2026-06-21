# Mobile Android RL Guide (Complete)

This is the current onboarding and operations guide for the repo after the improvement-plan implementation and live revalidation work.

Related docs:

- [Improvement Plan](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPROVEMENT_PLAN.md)
- [Implementation Report](/data/Balram/prime-intellect-android-adk-rl-environments/docs/MOBILE_RL_IMPLEMENTATION_REPORT.md)
- [Reward Semantics](/data/Balram/prime-intellect-android-adk-rl-environments/docs/REWARDS.md)
- [Observation / Action Schema](/data/Balram/prime-intellect-android-adk-rl-environments/docs/OBSERVATION_ACTION_SCHEMA.md)

## Current Reality

Implemented and verified:

- ADB-backed benchmark and rollout orchestration
- device-pool logic
- snapshot/full reset plumbing
- real emulator preflight
- real demo-APK form-task execution
- real benchmark artifact generation
- real rollout artifact generation

Current live result on the demo APK:

- form tasks pass
- ride tasks fail
- benchmark quick run score: `0.5`
- rollout score: `0.5`

Artifacts from the latest real run:

- benchmark: `artifacts/benchmarks/proof-quick/20260621_171854`
- rollout: `artifacts/runs/20260621_172107`

## Main Entry Surface

Use the orchestrator:

- [scripts/mobile_rl.sh](/data/Balram/prime-intellect-android-adk-rl-environments/scripts/mobile_rl.sh)

Supported commands:

- `preflight`
- `health`
- `benchmark proof|quick|release`
- `rollout`
- `prime-eval`
- `android-world`
- `pipeline`

Defaults come from:

- [configs/mobile/orchestrator.env](/data/Balram/prime-intellect-android-adk-rl-environments/configs/mobile/orchestrator.env)

Environment variables override config defaults at runtime.

## Recommended Environment

```bash
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_HOME=$ANDROID_SDK_ROOT
export ANDROID_AVD_HOME=/data/Balram/prime-intellect-android-adk-rl-environments/.deps/android_avd
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"
export ADB_SERIAL=127.0.0.1:15555
export RESET_MODE=full
export ADB_CMD_TIMEOUT_S=60
export MOBILE_REQUIRE_KVM=0
```

## Recommended Workflow

1. `make mobile-help`
2. `POOL_SIZE=1 ./scripts/mobile_preflight.sh`
3. `./scripts/mobile_rl.sh benchmark quick --attempts 1 --pool-size 1`
4. `./scripts/mobile_rl.sh rollout --pool-size 1 --no-openai --json`

## Exact Commands Used In Live Validation

Preflight:

```bash
export ADB_SERIAL=127.0.0.1:15555
export RESET_MODE=full
export ADB_CMD_TIMEOUT_S=60
POOL_SIZE=1 MOBILE_REQUIRE_KVM=0 ./scripts/mobile_preflight.sh
```

Benchmark:

```bash
ADB_SERIAL=127.0.0.1:15555 RESET_MODE=full ADB_CMD_TIMEOUT_S=60 \
./scripts/mobile_rl.sh benchmark quick --attempts 1 --pool-size 1
```

Rollout:

```bash
ADB_SERIAL=127.0.0.1:15555 RESET_MODE=full ADB_CMD_TIMEOUT_S=60 \
./scripts/mobile_rl.sh rollout --pool-size 1 --no-openai --json
```

## What To Expect

Preflight output:

- `serial=...`
- `api_level=...`
- `boot_completed=1`

Benchmark output:

- JSON summary or human-readable summary
- `output_dir=artifacts/benchmarks/...`

Rollout output:

- JSON summary or human-readable summary
- `artifacts=artifacts/runs/...`

## Artifact Layout

Rollout:

- `config.json`
- `summary.json`
- `rollout.jsonl`
- `reward_trace.jsonl`
- `replay.html`
- `device_info.json`
- `apk_info.json`
- `logcat.txt`

Benchmark:

- `summary.json`
- `task_results.jsonl`
- `metrics.json`
- `pass_at_k.json`
- `confidence_intervals.json` when enabled

## Current Limitation

The live ride-booking path still needs debugging. That is the remaining reason real runs currently land at `2/4` success rather than `4/4`.

## Architecture Notes

- Device allocation is lease-based and pool-aware.
- Reset logic is centralized in `reset_manager.py`.
- Observations are standardized to `mobile_observation.v1`.
- ADB runtime hardening now handles common emulator instability cases more gracefully.
