# Solution Implementation and Operations Guide

Last updated: 2026-06-22

This document is the practical solution handoff for the current mobile RL environment.

It explains:

- what problem this repo solves
- what was implemented
- how the implementation works end to end
- what was validated on real runtime paths
- how to run each supported workflow
- what still remains before a broader publication or production claim

## 1. Problem Statement

The goal of this repo is to provide a real Android reinforcement-learning and evaluation environment around the demo APK `com.primeintellect.dummyrl`.

The required solution was not just "run an APK with ADB". It needed to support:

- reliable real-device task execution
- reusable task specs
- structured reward verification from durable app state
- repeatable benchmark runs with artifacts
- multi-device pooling
- AndroidWorld interoperability
- Prime / `verifiers` compatibility

## 2. Final Solution Overview

The final solution combines four main layers:

1. A spec-driven task and eval layer
2. A hardened real-ADB execution layer
3. A benchmark and throughput measurement layer
4. Interop layers for AndroidWorld and Prime

At a high level:

```text
task spec
  -> eval runner / benchmark runner
  -> policy
  -> action schema validation
  -> environment
  -> ADB or AndroidWorld device backend
  -> dummy Android app
  -> shared-pref state readback
  -> reward + success verification
  -> metrics + artifacts
```

## 3. What Was Implemented

### New core runtime pieces

- `android_adk_rl_env/cli.py`
- `android_adk_rl_env/eval_runner.py`
- `android_adk_rl_env/task_specs.py`
- `android_adk_rl_env/benchmarking/pass_at_k.py`
- `android_adk_rl_env/benchmarking/reward_stats.py`
- `android_adk_rl_env/benchmarking/throughput.py`
- `android_adk_rl_env/tasks/checks/__init__.py`
- `android_adk_rl_env/tasks/checks/dummy_apk.py`
- `android_adk_rl_env/tasks/checks/ride_booking.py`

### New task spec assets

- `tasks/form_default.yaml`
- `tasks/form_randomized.yaml`
- `tasks/ride_cheapest.yaml`
- `tasks/ride_cancel.yaml`

### New or improved operator docs

- `docs/FULL_ARCHITECTURE_IMPLEMENTATION.md`
- `docs/THROUGHPUT_BENCHMARK.md`
- `docs/BENCHMARK_AND_ENVIRONMENT_CARD.md`
- `docs/PUBLICATION_READINESS_STATUS.md`
- `docs/PUBLICATION_RELEASE_PLAN.md`
- `docs/COMPETITIVE_POSITIONING.md`

### Existing files hardened

- `android_adk_rl_env/adb_device.py`
- `android_adk_rl_env/reset_manager.py`
- `android_adk_rl_env/proof_benchmark.py`
- `scripts/mobile_rl.sh`
- `scripts/run_android_world_openai.sh`
- `Makefile`

## 4. How The Main Parts Work

### 4.1 Task specs

Tasks are defined in YAML so eval and benchmark runs use the same contract.

Each task spec defines:

- task identity
- target package / APK
- goal
- step limit
- success check
- reward mode
- task parameters

This removes hardcoded benchmark-only logic and lets the runtime treat form and ride tasks consistently.

### 4.2 Eval runner

`android_adk_rl_env/eval_runner.py` is the shared execution path behind CLI evals and benchmarks.

It does the following:

```text
load task spec
  -> resolve device serial
  -> run health check
  -> install APK if needed
  -> reset environment
  -> execute policy
  -> read durable state
  -> compute reward and exact success
  -> return structured result
```

### 4.3 ADB execution layer

`android_adk_rl_env/adb_device.py` is the live device integration layer.

It is responsible for:

- shell commands
- install / launch / force-stop / clear-data
- fresh UIAutomator dumps
- resource lookup
- text entry
- taps and swipes
- shared-preference readback

Important reliability fixes added here:

- configurable ADB command timeout
- fresh dump preferred over stale dump
- fallback dump handling when `uiautomator dump` is flaky
- foreground-package checks before UI interaction
- dismissal of blocking system dialogs
- scroll-aware resource discovery for offscreen controls

### 4.4 Reset strategy

`android_adk_rl_env/reset_manager.py` supports:

- `full`
- `snapshot`

Current reliable live path:

- `full`

Why snapshot needed hardening:

- the main validated emulator path used ADB-over-TCP serial `127.0.0.1:15555`
- that serial is not a console-style `emulator-####` serial
- emulator snapshot console commands are not reliable there

Fix:

- snapshot support now checks whether emulator-console control is actually available
- unsupported TCP emulator serials degrade directly to `full` reset instead of repeatedly attempting invalid snapshot commands

### 4.5 Reward and verifier design

Rewards are not inferred from screenshots.

They are read from durable app state in shared preferences and then passed through registered verifier functions.

This gives:

- fractional shaped reward
- sparse exact final reward
- deterministic success checks for benchmarking

Current verifier coverage includes:

- exact form success
- fractional form reward
- exact ride success
- fractional ride reward

### 4.6 Benchmarking layer

`android_adk_rl_env/proof_benchmark.py` and `android_adk_rl_env/benchmarking/` provide:

- repeated task execution
- artifact writing
- pass@k
- reward summaries
- best-of-k summaries
- throughput measurements

The benchmark rows now also capture per-attempt timing and device serial information, which made real pool validation possible.

### 4.7 AndroidWorld integration

AndroidWorld support is wired through:

- `android_adk_rl_env/android_world_bridge.py`
- `android_adk_rl_env/android_world_runner.py`

How it works:

- AndroidWorld handles the Android interaction layer
- this repo still uses the app's durable state as the reward source of truth
- the same underlying task logic remains aligned with the ADB path

Important runtime requirement:

- the emulator must expose a gRPC port such as `-grpc 8555`

### 4.8 Prime integration

Prime compatibility is provided through:

- `prime_android_adk_rl_env/`
- `environments/mobile_android_rl/`
- `scripts/run_prime_eval_android_adk.sh`

This allows the environment to be launched by Prime / `verifiers` while preserving the mobile task semantics and reward outputs.

## 5. What Was Validated

## Real ADB evals

Validated on 2026-06-22:

- serial: `127.0.0.1:15555`
- Android API: `34`
- package: `com.primeintellect.dummyrl`

Observed task results:

- `form_default`: success
- `form_randomized`: success
- `ride_cheapest`: success
- `ride_cancel`: success

## Device pool validation

Validated on 2026-06-22:

- pool size: `2`
- serials:
  - `127.0.0.1:15555`
  - `emulator-5556`
- overlapping timestamps: confirmed
- artifact:
  - `artifacts/benchmarks/pool2-validate/20260622_052518`

## Release-style benchmark validation

Validated on 2026-06-22:

- samples per task: `10`
- total attempts: `40`
- exact success rate: `1.0`
- pass@1: `1.0`
- pass@2: `1.0`
- pass@3: `1.0`
- pass@5: `1.0`
- pass@10: `1.0`
- artifact:
  - `artifacts/benchmarks/publication-live-pool2/20260622_052711`

## Throughput validation

Measured on 2026-06-22:

- pool `1`:
  - rollouts/sec `0.0294`
  - env-steps/sec `0.1395`
  - avg reset `9.2095s`
- pool `2`:
  - rollouts/sec `0.0604`
  - env-steps/sec `0.2870`
  - avg reset `9.1848s`
  - scaling efficiency `1.0285`

Artifact:

- `artifacts/throughput/publication/throughput_summary.json`

## AndroidWorld validation

Validated on 2026-06-22:

- backend: `android_world`
- policy: `scripted`
- success rate: `1.0`
- artifact:
  - `artifacts/android_world/scripted_smoke.jsonl`

## Prime validation

Validated on 2026-06-22 as a live runnable path:

- script:
  - `scripts/run_prime_eval_android_adk.sh`
- artifact:
  - `artifacts/prime_eval_android_adk/live_20260622/prime_eval.log`

Observed result:

- harness completed
- reward: `0.0`
- turns: `6`

Meaning:

- Prime integration is runnable with a real model-backed live eval
- the current model behavior is not yet reliable enough to claim task success on the validated live run

## Live calibration contrast

Validated on 2026-06-22:

- oracle/scripted benchmark:
  - `artifacts/benchmarks/publication-live-pool2/20260622_052711`
  - exact success rate `1.0`
  - pass@1 through pass@10 `1.0`
- bounded bad-policy benchmark:
  - `artifacts/benchmarks/broken-live-form/20260622_095050`
  - exact success rate `0.0`
  - pass@1 `0.0`
  - pass@2 `0.0`
  - pass@3 `0.0`
  - shaped reward mean `0.15`
  - form-task scope only
- bounded bad-policy benchmark for ride tasks:
  - `artifacts/benchmarks/broken-live-ride/20260622_115043`
  - exact success rate `0.0`
  - pass@1 `0.0`
  - pass@2 `0.0`
  - pass@3 `0.0`
  - shaped reward mean `0.18`

Meaning:

- the live benchmark path now has a real all-success oracle batch
- it also has real all-failure bounded-policy batches for both form and ride families
- this proves the live pass@k wiring discriminates in practice, not only in unit tests
- ride shaped reward was tightened so broken policies no longer receive half-credit for trivial partial progress

## 6. How To Run Everything

### Base environment

Recommended env setup:

```bash
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_HOME=$ANDROID_SDK_ROOT
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"
export RESET_MODE=full
export ADB_CMD_TIMEOUT_S=60
```

If using the current main emulator path:

```bash
export ADB_SERIAL=127.0.0.1:15555
```

### Health check

```bash
python3 -m android_adk_rl_env.cli health --compact
```

### Live scripted evals

```bash
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted --compact --no-install-apk
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/form_randomized.yaml --policy scripted --compact --no-install-apk
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/ride_cheapest.yaml --policy scripted --compact --no-install-apk
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/ride_cancel.yaml --policy scripted --compact --no-install-apk
```

### Proof benchmark

```bash
RESET_MODE=full ADB_SERIALS='127.0.0.1:15555 emulator-5556' \
python3 -m android_adk_rl_env.proof_benchmark \
  --tasks-dir tasks \
  --attempts-per-instance 10 \
  --pass-k 1 2 3 5 10 \
  --pool-size 2 \
  --output artifacts/benchmarks/publication-live-pool2 \
  --compact
```

### Throughput benchmark

```bash
python3 -m android_adk_rl_env.benchmarking.throughput \
  --pool-sizes 1 2 \
  --attempts-per-instance 1 \
  --pass-k 1 \
  --output artifacts/throughput/publication \
  --compact
```

### AndroidWorld scripted run

Start a gRPC-enabled emulator first, then run:

```bash
./.venv/bin/python -B -m android_adk_rl_env.android_world_runner \
  --backend android_world \
  --policy scripted \
  --episodes 1 \
  --max-steps 10 \
  --output artifacts/android_world/scripted_smoke.jsonl \
  --adb-path adb \
  --adb-serial emulator-5556 \
  --console-port 5556 \
  --grpc-port 8555 \
  --compact
```

Equivalent script entrypoint:

```bash
env POLICY=scripted START_EMULATOR=0 STOP_EMULATOR_AFTER_RUN=0 ADB_SERIAL=emulator-5556 CONSOLE_PORT=5556 GRPC_PORT=8555 ./scripts/run_android_world_openai.sh
```

### Prime eval

```bash
env ADB_SERIAL=127.0.0.1:15555 START_EMULATOR=0 STOP_EMULATOR_AFTER_RUN=0 RESULTS_DIR=artifacts/prime_eval_android_adk/live_20260622 ./scripts/run_prime_eval_android_adk.sh
```

### Tests

```bash
python3 -m unittest discover -s tests/unit
python3 -m unittest discover -s tests/integration
python3 -m unittest discover -s tests/android_world
python3 -m unittest discover -s tests/prime
```

## 7. What Is Working Today

- real ADB task execution
- YAML task-spec driven eval
- deterministic reward verification from app state
- benchmark artifact generation
- pool-size `2` concurrent execution
- throughput measurement
- AndroidWorld scripted path
- Prime live eval as a runnable harness path
- live pass@k discrimination between oracle and bad-policy runs

## 8. What Still Needs More Work

- stronger model behavior for Prime / model-based live success
- AndroidWorld OpenAI validation
- pool sizes above `2`
- cross-app benchmark families
- training curves and before/after model comparisons
- broader publication comparison tables

## 9. Recommended Read Order

1. `docs/SOLUTION_IMPLEMENTATION_AND_OPERATIONS.md`
2. `docs/FULL_ARCHITECTURE_IMPLEMENTATION.md`
3. `docs/PUBLICATION_READINESS_STATUS.md`
4. `docs/THROUGHPUT_BENCHMARK.md`
5. `docs/BENCHMARK_AND_ENVIRONMENT_CARD.md`
6. `IMPLEMENTED_AND_WORKING.md`
