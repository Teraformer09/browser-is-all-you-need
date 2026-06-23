# Architecture Guide

Last updated: 2026-06-12

This guide explains the system architecture of the Mobile Android RL Environment.

## High-Level Architecture

```text
Taskset JSONL
  -> Task object
  -> Environment
  -> Observation builder
  -> Policy/model
  -> Strict action parser
  -> Safety policy
  -> Device backend
  -> Android app state
  -> Reward verifier
  -> Artifact writer
```

## Main Packages

```text
android_adk_rl_env/
  cli.py
  eval_runner.py
  proof_benchmark.py
  rollout_runner.py
  apk_env.py
  android_world_bridge.py
  reset_manager.py
  task_specs.py
  device_pool.py
  core/
  devices/
  envs/
  policies/
  tasks/
  training/
  benchmarking/

prime_android_adk_rl_env/
dummy_android_app/
tasks/
scripts/
tests/
```

## Core Layer

The core layer is backend-independent.

```text
android_adk_rl_env/core/actions.py        Strict canonical action schema
android_adk_rl_env/core/observations.py  Observation builders
android_adk_rl_env/core/reward.py        Reward helpers
android_adk_rl_env/core/artifacts.py     Run artifact writer
android_adk_rl_env/core/safety.py        Safety policy
android_adk_rl_env/core/task.py          JSONL task loading
android_adk_rl_env/core/rollout.py       Rollout row helper
android_adk_rl_env/core/errors.py        Runtime error types
```

The core rule: this layer should not depend on ADB, AndroidWorld, Prime, OpenAI, or Android SDK.

## Action Architecture

Model-facing action:

```json
{
  "type": "tap_element",
  "element_id": "submit_button",
  "x": null,
  "y": null,
  "text": null,
  "x1": null,
  "y1": null,
  "x2": null,
  "y2": null,
  "duration_ms": null
}
```

Internal compatibility action:

```json
{
  "action": "click_resource",
  "target": "submit_button",
  "text": null
}
```

Mapping:

```text
tap_element      -> click_resource
type_text        -> input_resource
tap_coordinates  -> coordinate tap
press_back       -> Android back
press_home       -> Android home
swipe            -> swipe/scroll
wait             -> sleep/wait action
finish           -> terminal status action
```

## Environment Layer

Main environment:

```text
android_adk_rl_env/apk_env.py
```

Responsibilities:

```text
reset
  -> create fresh episode
  -> reset device/app
  -> observe

step
  -> parse action
  -> validate schema
  -> apply safety policy
  -> execute through device
  -> observe
  -> calculate reward
  -> return StepResult
```

## Device Layer

Device backends implement app control and state reading.

```text
AdbDevice
  -> real emulator/device
  -> UIAutomator + ADB input
  -> SharedPreferences reward state

AndroidWorldDummyApkEnv
  -> AndroidWorld controller/AsyncEnv/JSONAction
  -> still reads reward state through ADB
```

## Reward Architecture

Rewards are durable-state based, not screenshot or model-text based.

Form task exact success:

```text
episode_id matches
query matches
name matches
email matches
submitted == true
screen == submitted
```

Reward concepts:

```text
reward          shaped reward for learning
final_reward    sparse exact reward
exact_success   benchmark pass/fail
components      per-field booleans
```

## Reset Architecture

ADB reset:

```text
adb shell am force-stop com.primeintellect.dummyrl
adb shell pm clear com.primeintellect.dummyrl
adb shell am start -W -S -n com.primeintellect.dummyrl/.MainActivity --es episode_id ...
wait for UI readiness
```

This prevents stale `SharedPreferences` from creating false reward.

## Observation Architecture

Compact observation:

```text
task
task_id
episode_id
screen
step
max_steps
elements
last_action
last_error
reward_components
exact_success
```

Full/screenshot observations add:

```text
ui tree
screenshot path
raw UI nodes
```

## Artifact Architecture

Artifact writer:

```text
android_adk_rl_env/core/artifacts.py
```

Output:

```text
artifacts/runs/{run_id}/
  config.json
  summary.json
  rollout.jsonl
  reward_trace.jsonl
  final_screen.png
  emulator_run.mp4
  replay.html
  logcat.txt
  device_info.json
  apk_info.json
```

Artifacts make rollout runs reviewable and benchmark runs reproducible.

## Prime Architecture

Prime/verifiers entry point:

```text
prime_android_adk_rl_env/
```

Prime-style package:

```text
environments/mobile_android_rl/
```

Loaders:

```python
load_environment(**kwargs)
load_taskset(split="eval", app="form")
load_harness(backend="adb")
```

Prime import must not require:

```text
ADB at import time
AndroidWorld at import time
OPENAI_API_KEY
connected device
```

## Docker Architecture

See [Docker Guide](/data/Balram/prime-intellect-android-adk-rl-environments/docs/DOCKER_GUIDE.md) for the canonical container workflows.

Host-ADB runner:

```text
Host:
  Android emulator + ADB server

Container:
  Python
  project dependencies
  ADB client
  Prime/verifiers
  tests/run commands
```

Files:

```text
Dockerfile.runner
docker-compose.yml
```

Full AndroidWorld image:

```text
Container:
  Android SDK
  emulator
  AndroidWorld
  Prime CLI
  repo package
```

Files:

```text
Dockerfile
compose.yaml
docker/
```

## Testing Architecture

```text
tests/unit/           no external services
tests/integration/    mocked-device integration + optional ADB
tests/android_world/  AndroidWorld import/mapping smoke
tests/prime/          Prime package import smoke
tests/test_*.py       legacy compatibility tests
```

Commands:

```bash
make test
make integration
make android-world
make prime
python3 -m unittest discover -s tests
```

## Extension Points

Add a task:

```text
environments/mobile_android_rl/mobile_android_rl/tasks/*.jsonl
```

Add a reward:

```text
android_adk_rl_env/tasks/
```

Add a backend:

```text
android_adk_rl_env/devices/
android_adk_rl_env/envs/mobile_task_env.py
```

Add a policy:

```text
android_adk_rl_env/policies/
```

Add artifact output:

```text
android_adk_rl_env/core/artifacts.py
```

## Current Boundaries

- Ride booking is represented by tasksets, a task/reward spec, and rollout replay flows.
- A full separate native ride-booking APK is not implemented yet.
- Full emulator-in-Docker execution requires KVM/nested virtualization.
- No real payment, ride booking, account, OTP, or personal-data workflow is included.
