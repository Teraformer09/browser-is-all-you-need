# System Overview and Operations Guide

Last updated: 2026-06-23

This document is the consolidated guide for the repository. It explains what the project is, how the runtime works end to end, how tasks are defined, how reward is computed, how the backends differ, and how to run the main workflows.

## What This Project Is

This repository implements a mobile Android RL and evaluation environment around the dummy APK `com.primeintellect.dummyrl`.

The system is built to answer one question reliably:

```text
Given a task, can an agent control a real Android app, complete the task,
and produce an auditable reward and artifact trail?
```

The main supported execution paths are:

```text
ADB-backed real device/emulator execution
AndroidWorld-backed execution
Prime / verifiers environment integration
Spec-driven eval and benchmark CLIs
```

The project is not a toy simulator. The durable task signal comes from the APK's own persisted state, read back through ADB or the AndroidWorld bridge.

## The Core Runtime Loop

The environment works as a strict loop:

```text
Task spec or task object
  -> Reset the app/device
  -> Build an observation from UI + durable APK state
  -> Policy/model emits one structured action
  -> Action is validated and safety-checked
  -> Backend executes the action
  -> APK state is read again
  -> Reward is computed
  -> Step result and artifacts are emitted
```

At the code level, the main step result shape is `StepResult` from `android_adk_rl_env/env.py`.

## Package Map

```text
android_adk_rl_env/
  cli.py                 Unified `mobile-rl` CLI
  eval_runner.py         Shared eval and healthcheck logic
  proof_benchmark.py     pass@k benchmark runner
  rollout_runner.py      Standard rollout suite and artifacts
  apk_env.py             Step-based APK environment
  android_world_bridge.py AndroidWorld backend bridge
  adb_device.py          ADB/UIAutomator device controller
  reset_manager.py       Snapshot/full reset orchestration
  task_specs.py          YAML task-spec loader
  device_pool.py         Pool-aware device allocation
  core/                  Actions, observations, reward, artifacts, safety
  tasks/                 Dummy APK and ride-booking tasks
  policies/              Scripted, random, OpenAI, local RL, VLM screenshot policies
  benchmarking/          pass@k and reward reporting helpers
  training/              Rollout and local RL helpers

prime_android_adk_rl_env/
  prime_android_adk_rl_env.py  Prime/verifiers environment implementation
  load_environment.py          Compatibility loader
  prime_env.py                 Export surface

dummy_android_app/
  Real Android app source code

tasks/
  YAML task specs used by the CLI benchmark path

tests/
  Unit, integration, AndroidWorld, and Prime tests
```

## Main Concepts

### 1. Tasks

There are two primary task families in the repo:

```text
Dummy form search and submit
Ride booking
```

These are implemented as task objects, not hard-coded scripts. The main task classes are:

```text
android_adk_rl_env/tasks/dummy_apk.py
android_adk_rl_env/tasks/ride_booking.py
```

Each task defines:

```text
goal text
resource IDs that actions are allowed to target
expected durable state in SharedPreferences
reward calculation rules
scripted baseline trajectory
```

### 2. Actions

The model-facing action schema is strict and JSON-based. It is defined in `android_adk_rl_env/core/actions.py`.

Supported action types:

```text
tap_element
tap_coordinates
type_text
press_back
press_home
swipe
wait
finish
```

The environment converts those into the backend-specific execution form. Older compatibility names like `click_resource` and `input_resource` are still accepted internally.

Example action:

```json
{
  "type": "tap_element",
  "element_id": "submit_button",
  "text": null,
  "x": null,
  "y": null,
  "x1": null,
  "y1": null,
  "x2": null,
  "y2": null,
  "duration_ms": null
}
```

### 3. Observations

Observations are assembled from:

```text
current UI tree or nodes
durable APK state from SharedPreferences
current step count
last action
last error
reward and reward components
reset metadata
```

Observation assembly is handled by `android_adk_rl_env/core/observations.py`.

The observation modes are:

```text
compact_text
full_ui_tree
screenshot_only
hybrid
screenshot_ui_tree
```

### 4. Reward

Reward is state-based, not screenshot-based.

The form task, for example, checks durable state fields such as:

```text
episode_id
query
name
email
submitted
screen
```

The ride task checks fields such as:

```text
episode_id
ride_pickup
ride_drop
selected_ride
ride_confirmed or ride_cancelled
screen
```

Reward can be:

```text
shaped reward
final exact reward
success score for benchmark evaluation
```

The task decides what counts as exact success. The environment reads the result back from the task's verifier.

## How The Environment Works

The main real-device environment is `DummyApkEnv` in `android_adk_rl_env/apk_env.py`.

### Reset

Reset performs a full task/device reinitialization using `reset_manager.reset_task_device(...)`.

Reset behavior is controlled by `RESET_MODE`:

```text
snapshot
full
```

If snapshot mode is supported by the device, the reset manager can:

```text
create a baseline snapshot
restore the snapshot on later episodes
fall back to a full reset if snapshot restore fails
```

The full reset path is ADB-based:

```text
force-stop the app
clear app data
launch MainActivity with episode_id and launch extras
wait for UI readiness
```

### Step

Each step:

```text
parses or coerces the action
validates action schema
normalizes the target resource name
checks task-specific safety rules
executes the action through the backend
reads UI + SharedPreferences again
computes reward and success
returns StepResult
```

Important behavior:

```text
invalid actions receive a penalty
finish is only valid after exact success
safety blocks are tracked separately from schema errors
the episode ends on success, finish, or max_steps
```

### What The Environment Returns

The observation includes the most useful fields for debugging:

```text
task, task_id, episode_id
goal, package, surface, difficulty
steps, max_steps, done
ui and ui_tree_xml when available
last_action, last_error
expected_state, apk_state
reward_components
reward, final_reward, exact_success
reset_metadata
```

## Backend Options

### ADB Backend

The default and most complete path is `AdbDevice` in `android_adk_rl_env/adb_device.py`.

It supports:

```text
wait for boot completion
install APKs
launch and reset the app
click resource IDs
input text
press back/home
swipe and tap coordinates
dump UIAutomator XML
read SharedPreferences
snapshot save/restore on emulator-backed devices
```

This is the path used by the CLI eval and benchmark flows.

### AndroidWorld Backend

`android_adk_rl_env/android_world_bridge.py` keeps AndroidWorld optional.

When enabled, the system:

```text
creates an AndroidWorld controller
executes JSON actions through AndroidWorld
still reads durable reward state from the APK
keeps the same task success contract as ADB
```

This keeps the evaluation semantics aligned while swapping only the interaction layer.

### Prime / Verifiers Backend

`prime_android_adk_rl_env/prime_android_adk_rl_env.py` exposes a `vf.MultiTurnEnv` environment for Prime-style usage.

It:

```text
creates the task and environment
provides a fixed system prompt
accepts one JSON action per turn
returns compact observations
tracks Android-specific state in the verifier state
stops when the APK final reward reaches 1.0
```

The Prime path can use either:

```text
ADB backend
AndroidWorld backend
```

depending on the `backend` argument.

## Task Specs

The CLI benchmark and spec-driven eval paths use YAML files from `tasks/`.

Example fields:

```yaml
task_id: form_default
benchmark_family: form_default
task_type: dummy_form
policy_hint: scripted
tags:
  - benchmark
app:
  package: com.primeintellect.dummyrl
  apk_path: dummy_android_app/build/out/dummy-rl-app.apk
setup:
  start_screen: home
  difficulty: easy
goal: Search for "airport ride", enter "Ada Lovelace" and "ada@example.com", then submit the form.
max_steps: 12
success:
  type: registered_check
  check: dummy_form_exact
  threshold: 1.0
reward:
  mode: fractional
parameters:
  query: airport ride
  name: Ada Lovelace
  email: ada@example.com
```

Task specs are loaded by `android_adk_rl_env/task_specs.py`.

Known task types:

```text
dummy_form
ride_booking
```

## CLI Workflows

The main entry point is:

```bash
python3 -m android_adk_rl_env.cli --help
```

### Health Check

```bash
python3 -m android_adk_rl_env.cli health
```

This checks the ADB connection, boot state, and whether the target package is installed.

### Single Task Eval

```bash
python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted
```

This loads one task spec, builds the task object, installs the APK if requested, runs the policy, and returns a JSON result.

### Benchmark

```bash
python3 -m android_adk_rl_env.cli benchmark --tasks-dir tasks --samples-per-task 10 --pass-k 1 2 3 5 10
```

This runs the benchmark task specs multiple times, computes `pass@k`, and writes benchmark artifacts.

## Rollouts And Benchmarks

### Rollout Suite

`android_adk_rl_env/rollout_runner.py` runs a curated rollout suite and writes standardized artifacts.

It includes:

```text
form tasks
ride tasks
optional OpenAI-backed form rollout when OPENAI_API_KEY is set
```

### Proof Benchmark

`android_adk_rl_env/proof_benchmark.py` runs repeated attempts per task and computes:

```text
exact success rate
average reward
average steps
pass@k
confidence intervals
reward calibration summaries
```

The benchmark path also uses `DevicePool` to lease devices for concurrent execution.

## Artifacts

Artifacts are written under `artifacts/runs/{run_id}` or `artifacts/benchmarks/{run_id}` depending on the workflow.

Typical rollout artifacts:

```text
config.json
summary.json
rollout.jsonl
reward_trace.jsonl
replay.html
device_info.json
apk_info.json
logcat.txt
final_screen.png
emulator_run.mp4
```

Benchmark artifacts also include:

```text
task_results.jsonl
pass_at_k.json
reward_report.json
reward_calibration.json (when enabled)
```

The artifact writer lives in `android_adk_rl_env/core/artifacts.py`.

## Device Pooling

`android_adk_rl_env/device_pool.py` gives the benchmark and rollout systems a simple lease-based pool.

Behavior:

```text
derive serials from ADB_SERIALS, ADB_SERIAL, or emulator defaults
mark leased devices busy
release them back to idle after each run
assign console and gRPC ports for emulator-backed pools
```

This is how the benchmark runner supports multiple devices without sharing a single serial across concurrent attempts.

## Scripted Baselines

The tasks include scripted execution paths. These are useful for:

```text
smoke testing
ground-truth demonstration
benchmark calibration
debugging task specs and reward logic
```

The scripted trajectories are defined in the task classes and are used by the CLI and rollout suite when `--policy scripted` is selected.

## Environment Variables

Common variables:

```bash
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_HOME=$ANDROID_SDK_ROOT
export ANDROID_AVD_HOME=/data/Balram/prime-intellect-android-adk-rl-environments/.deps/android_avd
export PATH="$ANDROID_SDK_ROOT/platform-tools:$PATH"
export ADB_SERIAL=127.0.0.1:15555
export RESET_MODE=full
export ADB_CMD_TIMEOUT_S=60
```

Useful optional variables:

```text
POOL_SIZE
ADB_SERIALS
ADB_BASE_CONSOLE_PORT
ADB_BASE_GRPC_PORT
ADB_BASELINE_SNAPSHOT
OPENAI_API_KEY
ANDROID_WORLD_A11Y_METHOD
ROLLOUT_BACKEND
BENCHMARK_SAMPLES_PER_TASK
```

## Validation And Tests

The repository ships with unit, integration, AndroidWorld, and Prime tests.

Common commands:

```bash
make test
make integration
make android-world
make prime
```

For ADB-backed integration paths, some tests are opt-in and require a real connected emulator/device.

## Operational Model

If you need to understand the system quickly, follow this order:

```text
1. Read the task spec or task class
2. Read the action schema
3. Read the environment reset/step logic
4. Read the task reward verifier
5. Read the device backend
6. Read the CLI runner or benchmark runner
7. Inspect the emitted artifacts
```

That sequence matches the actual control flow and makes it easier to debug failures.

## Practical Summary

The project is organized around three guarantees:

```text
strict actions
durable rewards
auditable runs
```

If a run succeeds, you should be able to explain:

```text
what task was run
what exact UI actions were taken
what device/app state changed
why reward was assigned
what files prove the result
```

That is the system this repository implements.
