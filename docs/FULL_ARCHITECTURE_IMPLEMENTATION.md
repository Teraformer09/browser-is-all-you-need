# Full Architecture and Implementation Guide

Last updated: 2026-06-22

This document is the single full-reference guide for the current mobile RL environment.

It explains:

- the system architecture
- what was added during the implementation and go-live upgrade
- how the runtime works
- how to run each supported path
- what results were actually observed
- what is implemented versus what is fully validated

## 1. System Goal

This repository provides a real Android RL and evaluation environment around the demo APK `com.primeintellect.dummyrl`.

The system supports:

- real ADB-backed task execution
- spec-driven evaluation through a unified CLI
- benchmark-style repeated execution and metric reporting
- Prime / `verifiers` compatibility
- AndroidWorld integration surfaces
- durable-state reward verification from the app itself

## 2. Current Top-Level Architecture

```text
YAML task spec or JSONL taskset
  -> task loader / task factory
  -> task object
  -> environment or scripted executor
  -> observation builder
  -> policy
  -> strict action schema
  -> safety checks
  -> device backend
  -> real Android app
  -> durable state readback
  -> reward verifier
  -> eval / benchmark result
  -> artifacts and metrics
```

## 3. Main Repository Structure

```text
android_adk_rl_env/
  cli.py
  eval_runner.py
  proof_benchmark.py
  task_specs.py
  adb_device.py
  apk_env.py
  reset_manager.py
  device_pool.py
  android_world_bridge.py
  rollout_runner.py
  benchmarking/
  core/
  policies/
  tasks/

prime_android_adk_rl_env/
environments/mobile_android_rl/
dummy_android_app/
tasks/
scripts/
configs/mobile/
tests/
docs/
```

## 4. Main Runtime Components

### 4.1 CLI Layer

Primary entrypoint:

```text
android_adk_rl_env/cli.py
```

Supported commands:

- `mobile-rl health`
- `mobile-rl eval`
- `mobile-rl benchmark`

Equivalent Python entrypoint:

```bash
python3 -m android_adk_rl_env.cli
```

Purpose:

- gives one operator-facing interface for health checks, task evals, and benchmarks
- standardizes structured JSON output
- keeps harness-success separate from task-success

### 4.2 Task Spec Layer

Files:

```text
android_adk_rl_env/task_specs.py
tasks/form_default.yaml
tasks/form_randomized.yaml
tasks/ride_cheapest.yaml
tasks/ride_cancel.yaml
```

Purpose:

- define runnable tasks as YAML
- decouple task execution from hardcoded Python benchmark definitions
- make eval and benchmark paths share the same task contract

Task spec includes:

- `task_id`
- `task_type`
- `app.package`
- `app.apk_path`
- `goal`
- `max_steps`
- `success.type`
- `success.check`
- `success.threshold`
- `reward.mode`
- task-specific `parameters`

### 4.3 Eval Execution Layer

File:

```text
android_adk_rl_env/eval_runner.py
```

Purpose:

- shared runtime used by CLI eval and benchmark execution
- loads task specs
- resolves device serial
- runs device health check
- executes scripted or model-backed policy path
- computes task success and reward output

### 4.4 Device Layer

Main file:

```text
android_adk_rl_env/adb_device.py
```

Responsibilities:

- ADB command execution
- app install / launch / reset
- UIAutomator dump collection
- resource lookup
- text input and taps
- scroll-based discovery for offscreen controls
- durable state readback from app shared prefs

Important hardening now present:

- configurable ADB command timeout
- fresh UI dump preferred over stale cached dump
- cached XML fallback only when fresh dump is flaky
- blocking Android system dialogs dismissed
- package focus checks before UI interaction
- scroll-to-find lookup for controls not initially visible

### 4.5 Reset Layer

Main file:

```text
android_adk_rl_env/reset_manager.py
```

Reset modes:

- `snapshot`
- `full`

Current behavior:

- snapshot reset is attempted when enabled and supported
- if snapshot creation or restore fails, reset falls back to full reset
- full reset remains the reliable live path on the current emulator

Full reset flow:

```text
force-stop app
  -> clear app data
  -> launch app with episode/task extras
  -> wait for UI readiness
```

### 4.6 Environment Layer

Main file:

```text
android_adk_rl_env/apk_env.py
```

Purpose:

- step-based RL environment for model-driven execution
- parses actions
- applies safety policy
- executes device actions
- builds observations
- calculates shaped and final rewards

### 4.7 Observation and Action Schema

Main files:

```text
android_adk_rl_env/core/actions.py
android_adk_rl_env/core/observations.py
docs/OBSERVATION_ACTION_SCHEMA.md
```

Canonical action schema supports:

- `tap_element`
- `tap_coordinates`
- `type_text`
- `press_back`
- `press_home`
- `swipe`
- `wait`
- `finish`

Observation schema:

- `schema_version`
- `task`
- `task_id`
- `episode_id`
- `screen`
- `step`
- `max_steps`
- `elements`
- `last_action`
- `last_error`
- `reward`
- `final_reward`
- `exact_success`
- `reward_components`

### 4.8 Reward Layer

Main files:

```text
android_adk_rl_env/tasks/dummy_apk.py
android_adk_rl_env/tasks/ride_booking.py
android_adk_rl_env/tasks/checks/
android_adk_rl_env/benchmarking/reward_stats.py
docs/REWARDS.md
```

Reward design:

- rewards come from durable app state, not screenshots
- `reward` is shaped / fractional
- `final_reward` is exact sparse success
- `task_success` comes from task-spec success check plus threshold

Registered checks now exist for:

- exact form success
- fractional form reward
- exact ride success
- fractional ride reward

### 4.9 Benchmarking Layer

Main files:

```text
android_adk_rl_env/proof_benchmark.py
android_adk_rl_env/benchmarking/pass_at_k.py
android_adk_rl_env/benchmarking/reward_stats.py
```

Added capabilities:

- task-spec driven benchmark execution
- strict unbiased `pass@k`
- `k={1,2,3,5,10}` support
- per-task reward summaries
- best-of-k reward summaries
- reward calibration helpers
- bootstrap confidence interval helpers

Important semantics:

- `pass@k` raises if `k > n`
- task success is averaged across tasks, not guessed from one sample

### 4.10 Prime Layer

Main areas:

```text
prime_android_adk_rl_env/
environments/mobile_android_rl/
```

Purpose:

- expose Prime / `verifiers` compatible environment entrypoints
- keep import-time dependencies light
- preserve compatibility with taskset loading and environment loading

## 5. What Was Added

The main implementation additions for the go-live upgrade were:

### Core additions

- `android_adk_rl_env/cli.py`
- `android_adk_rl_env/eval_runner.py`
- `android_adk_rl_env/task_specs.py`
- `android_adk_rl_env/benchmarking/pass_at_k.py`
- `android_adk_rl_env/benchmarking/reward_stats.py`
- `android_adk_rl_env/tasks/checks/__init__.py`
- `android_adk_rl_env/tasks/checks/dummy_apk.py`
- `android_adk_rl_env/tasks/checks/ride_booking.py`

### New task specs

- `tasks/form_default.yaml`
- `tasks/form_randomized.yaml`
- `tasks/ride_cheapest.yaml`
- `tasks/ride_cancel.yaml`

### Test coverage added

- `tests/unit/test_pass_at_k.py`
- `tests/unit/test_reward_calibration.py`
- `tests/unit/test_task_specs.py`

### Existing files extended or hardened

- `android_adk_rl_env/adb_device.py`
- `android_adk_rl_env/reset_manager.py`
- `android_adk_rl_env/proof_benchmark.py`
- `android_adk_rl_env/tasks/dummy_apk.py`
- `Makefile`
- `pyproject.toml`
- `configs/mobile/orchestrator.env`

## 6. How the Main Paths Work

### 6.1 Health Path

Command:

```bash
python3 -m android_adk_rl_env.cli health
```

Flow:

```text
resolve adb serial
  -> wait for device
  -> read Android API level
  -> check boot completion
  -> check package install status
  -> print structured JSON
```

### 6.2 Eval Path

Command shape:

```bash
python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted
```

Flow:

```text
load YAML task spec
  -> build known task object
  -> resolve device
  -> optional health check
  -> optional APK install
  -> reset task/app
  -> execute scripted or model policy
  -> read durable state
  -> run success check
  -> emit JSON result
```

Exit semantics:

- exit code `0` means harness succeeded
- task may still succeed or fail inside that successful harness run
- non-zero exit means harness/runtime failure

### 6.3 Benchmark Path

Command shape:

```bash
python3 -m android_adk_rl_env.cli benchmark --tasks-dir tasks --samples-per-task 10 --pass-k 1 2 3 5 10
```

Flow:

```text
load task specs
  -> repeat each task N times
  -> run each through shared eval runner
  -> group results by task
  -> compute pass@k
  -> compute reward distribution summaries
  -> optionally compute calibration reports
  -> write benchmark artifacts
```

## 7. How To Run

### 7.1 Environment setup

Recommended shell setup:

```bash
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_HOME=$ANDROID_SDK_ROOT
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"
export ADB_SERIAL=127.0.0.1:15555
export RESET_MODE=full
export ADB_CMD_TIMEOUT_S=60
```

### 7.2 Install package entrypoint

If installed as a package:

```bash
mobile-rl --help
```

Without install:

```bash
python3 -m android_adk_rl_env.cli --help
```

### 7.3 Run health check

```bash
python3 -m android_adk_rl_env.cli health --compact
```

### 7.4 Run live evals

Form default:

```bash
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted --compact --no-install-apk
```

Form randomized:

```bash
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/form_randomized.yaml --policy scripted --compact --no-install-apk
```

Ride cheapest:

```bash
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/ride_cheapest.yaml --policy scripted --compact --no-install-apk
```

Ride cancel:

```bash
RESET_MODE=full python3 -m android_adk_rl_env.cli eval --task tasks/ride_cancel.yaml --policy scripted --compact --no-install-apk
```

### 7.5 Run tests

```bash
python3 -m unittest discover -s tests/unit
python3 -m unittest discover -s tests/integration
python3 -m unittest discover -s tests/android_world
python3 -m unittest discover -s tests/prime
```

### 7.6 Run benchmark

Current CLI form:

```bash
RESET_MODE=full python3 -m android_adk_rl_env.cli benchmark --tasks-dir tasks --samples-per-task 1 --pass-k 1 --output artifacts/benchmarks/live-smoke --compact
```

Note:

- benchmark logic is implemented
- a full clean live benchmark completion was not claimed in the current validation pass

## 8. Current Observed Results

Live validation performed on June 22, 2026:

- device serial: `127.0.0.1:15555`
- secondary pool serial: `emulator-5556`
- Android API: `34`
- package: `com.primeintellect.dummyrl`
- reset mode used for reliable live runs: `full`

### Health result

```text
serial=127.0.0.1:15555
api_level=34
boot_completed=1
package_installed=true
```

### Eval results

```text
form_default: harness_success=true, task_success=true, reward=1.0
form_randomized: harness_success=true, task_success=true, reward=1.0
ride_cheapest: harness_success=true, task_success=true, reward=1.0
ride_cancel: harness_success=true, task_success=true, reward=1.0
```

### Test results

```text
tests/unit: 37 passed
tests/integration: passed, 1 skipped
tests/android_world: passed
tests/prime: passed
```

### Pool validation result

```text
pool_size=2
serials=127.0.0.1:15555, emulator-5556
overlap_verified=true
artifact=artifacts/benchmarks/pool2-validate/20260622_052518
```

### Release benchmark result

```text
samples_per_task=10
total_attempts=40
exact_success_rate=1.0
pass@1=1.0
pass@2=1.0
pass@3=1.0
pass@5=1.0
pass@10=1.0
artifact=artifacts/benchmarks/publication-live-pool2/20260622_052711
```

### AndroidWorld scripted result

```text
backend=android_world
policy=scripted
episodes=1
success_rate=1.0
artifact=artifacts/android_world/scripted_smoke.jsonl
grpc_port=8555
```

## 9. What Is Implemented But Not Fully Revalidated

- OpenAI rollout collection through `android_adk_rl_env.train`
- Prime eval revalidation after the latest ADB/runtime hardening
- AndroidWorld OpenAI live revalidation after the latest ADB/runtime hardening
- multi-device hardware validation beyond `POOL_SIZE=2`

## 10. Practical Operator Notes

- On the current emulator, `RESET_MODE=full` is the reliable live path.
- Snapshot support exists, but unsupported snapshot save behavior should be treated as a performance optimization gap, not a correctness gap.
- For a single emulator, run live evals serially.
- Parallel live evals on one emulator can interfere with each other and create false failures.
- Offscreen controls are now discovered by scroll-aware lookup, which is important for the ride screens and smaller visible viewports.

## 11. Recommended Read Order

For a full understanding:

1. `docs/FULL_ARCHITECTURE_IMPLEMENTATION.md`
2. `docs/SOLUTION_IMPLEMENTATION_AND_OPERATIONS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/PUBLICATION_READINESS_STATUS.md`
5. `docs/CLI_BENCHMARK_REWARD_UPGRADE.md`
6. `docs/THROUGHPUT_BENCHMARK.md`
7. `docs/REWARDS.md`
8. `docs/OBSERVATION_ACTION_SCHEMA.md`
9. `IMPLEMENTED_AND_WORKING.md`
