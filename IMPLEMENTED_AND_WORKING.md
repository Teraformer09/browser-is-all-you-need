# Implemented And Working

Last updated: 2026-06-22

This file tracks what is implemented and what was actually validated in the current repo state.

It is intentionally strict:

- It only marks a path as verified if it was run successfully.
- It does not claim universal model compatibility.
- It does not claim full Prime Intellect parity unless that exact path is validated.

## Verified Working

- `mobile-rl health` ADB/device readiness check
- `mobile-rl eval` scripted form task path through YAML task spec
- `mobile-rl eval` scripted randomized form task path through YAML task spec
- `mobile-rl eval` scripted ride-booking task path through YAML task spec
- `mobile-rl eval` scripted ride-cancel task path through YAML task spec
- Real ADB-backed APK build and install
- Real scripted form task execution on emulator
- Real scripted ride-booking task execution on emulator
- Real scripted ride-cancel task execution on emulator
- Strict JSON action parsing and validation
- Reward verification from durable APK state
- Episode-safe reward checks with `episode_id`
- Device-pool logic and snapshot fallback behavior in automated tests
- Live `POOL_SIZE=2` benchmark execution on two real emulator serials
- Release-style benchmark run with `samples-per-task=10`
- Live AndroidWorld scripted execution on a gRPC-enabled emulator
- Throughput benchmark measurement for pool sizes `1` and `2`
- Live Prime `vf-eval` harness execution on the real environment
- Live broken-policy benchmark proving non-trivial pass@k discrimination

## Accurate Scope

What is true now:

- The validated runtime path works on a real emulator without using a fake backend.
- The current demo task set passes through the spec-driven CLI on a single real emulator.
- The current proof benchmark path has been validated on two concurrent emulator serials.
- AndroidWorld is installed and the scripted AndroidWorld path is validated on a live emulator.
- Prime live eval is validated as a runnable harness path.
- The live benchmark path now has both an all-success oracle batch and a live all-failure bounded-policy batch.
- The repo is Prime-compatible in structure and entrypoints.
- The live form and ride flows are working on-device after the ADB/runtime hardening changes.

What is not claimed here:

- That Prime eval is already successful on the live model-backed path
- That AndroidWorld OpenAI execution was revalidated end to end in this session
- That multi-device pooling was hardware-validated beyond `POOL_SIZE=2`

## Commands Run Successfully

```bash
python3 -m android_adk_rl_env.cli health --compact
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted --compact --no-install-apk
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/form_randomized.yaml --policy scripted --compact --no-install-apk
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/ride_cheapest.yaml --policy scripted --compact --no-install-apk
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/ride_cancel.yaml --policy scripted --compact --no-install-apk
python3 -m unittest discover -s tests/unit
python3 -m unittest discover -s tests/integration
python3 -m unittest discover -s tests/android_world
python3 -m unittest discover -s tests/prime
RESET_MODE=full ADB_SERIALS='127.0.0.1:15555 emulator-5556' python3 -m android_adk_rl_env.proof_benchmark --tasks-dir tasks --attempts-per-instance 1 --pass-k 1 --pool-size 2 --output artifacts/benchmarks/pool2-validate --compact
RESET_MODE=full ADB_SERIALS='127.0.0.1:15555 emulator-5556' python3 -m android_adk_rl_env.proof_benchmark --tasks-dir tasks --attempts-per-instance 10 --pass-k 1 2 3 5 10 --pool-size 2 --output artifacts/benchmarks/publication-live-pool2 --compact
python3 -m android_adk_rl_env.benchmarking.throughput --pool-sizes 1 2 --attempts-per-instance 1 --pass-k 1 --output artifacts/throughput/publication --compact
./.venv/bin/python -B -m android_adk_rl_env.android_world_runner --backend android_world --policy scripted --episodes 1 --max-steps 10 --output artifacts/android_world/scripted_smoke.jsonl --adb-path adb --adb-serial emulator-5556 --console-port 5556 --grpc-port 8555 --compact
env ADB_SERIAL=127.0.0.1:15555 START_EMULATOR=0 STOP_EMULATOR_AFTER_RUN=0 RESULTS_DIR=artifacts/prime_eval_android_adk/live_20260622 ./scripts/run_prime_eval_android_adk.sh
env RESET_MODE=full ADB_SERIAL=127.0.0.1:15555 python3 -m android_adk_rl_env.proof_benchmark --tasks-dir artifacts/tmp_form_tasks --policy broken --attempts-per-instance 3 --pass-k 1 2 3 --pool-size 1 --output artifacts/benchmarks/broken-live-form --compact
```

## Real Emulator Validation

Validated on 2026-06-22 with:

- emulator serial: `127.0.0.1:15555`
- Android version: API 34
- package: `com.primeintellect.dummyrl`

Healthcheck result:

```text
serial=127.0.0.1:15555
api_level=34
boot_completed=1
package_installed=true
```

CLI eval results:

```text
form_default: harness_success=true, task_success=true, reward=1.0
form_randomized: harness_success=true, task_success=true, reward=1.0
ride_cheapest: harness_success=true, task_success=true, reward=1.0
ride_cancel: harness_success=true, task_success=true, reward=1.0
```

Pool validation result:

```text
pool_size=2
serials=127.0.0.1:15555, emulator-5556
overlap_verified=true
artifact=artifacts/benchmarks/pool2-validate/20260622_052518
```

Release benchmark result:

```text
samples_per_task=10
total_attempts=40
pass@1=1.0
pass@2=1.0
pass@3=1.0
pass@5=1.0
pass@10=1.0
artifact=artifacts/benchmarks/publication-live-pool2/20260622_052711
```

AndroidWorld scripted result:

```text
backend=android_world
policy=scripted
success_rate=1.0
artifact=artifacts/android_world/scripted_smoke.jsonl
```

Prime live eval result:

```text
backend=adb
model=gpt-4o-mini
harness_completed=true
reward=0.0
turns=6
artifact=artifacts/prime_eval_android_adk/live_20260622/prime_eval.log
```

Broken-policy live benchmark result:

```text
policy=broken
tasks=2
samples_per_task=3
total_attempts=6
exact_success_rate=0.0
pass@1=0.0
pass@2=0.0
pass@3=0.0
avg_reward=0.15
artifact=artifacts/benchmarks/broken-live-form/20260622_095050
```

Broken-policy live ride benchmark result:

```text
policy=broken
tasks=2
samples_per_task=3
total_attempts=6
exact_success_rate=0.0
pass@1=0.0
pass@2=0.0
pass@3=0.0
avg_reward=0.18
artifact=artifacts/benchmarks/broken-live-ride/20260622_115043
```

## Test Status

```text
tests/unit: 37 passed
tests/integration: passed, 1 skipped
tests/android_world: passed
tests/prime: passed
```

## Implemented But Not Fully Revalidated In This Session

- OpenAI rollout collection through `android_adk_rl_env.train`
- Prime eval success improvements beyond the currently validated runnable harness path
- AndroidWorld OpenAI run
- multi-device live rollout / benchmark with `POOL_SIZE > 2`

## Main Runtime Fixes Applied

- ADB command timeout is now configurable and higher by default
- stale cached UI dumps are no longer preferred over fresh dumps
- resource lookup now scrolls to discover offscreen controls on the single-emulator path
- UI dump handling now tolerates flaky `uiautomator` behavior better
- blocking Android system dialogs are actively dismissed
- package-foreground checks are used before resource lookup
- sourced orchestrator defaults now respect caller-provided env overrides
- live evals are now reliable when run serially on `POOL_SIZE=1`
