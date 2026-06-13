# Complete Tutorial: Mobile Android RL Environment

Last updated: 2026-06-12

Branch: `go-live-e2e-hardening`

This tutorial teaches the project from beginner level to advanced usage. By the end, you should understand how to run rollout workflows, inspect artifacts, add tasks, use the ADB/AndroidWorld/Prime paths, and reason about the architecture.

## 0. What This Project Is

This project is a reproducible RL/evaluation environment for mobile Android agents.

In plain terms:

```text
An agent gets a task.
The environment shows the current Android screen/UI state.
The agent returns one strict JSON action.
The backend executes that action on a real ADB device or AndroidWorld emulator.
The app writes durable state.
The environment reads that state and calculates reward.
The run writes artifacts for review.
```

The main proof path is the dummy Android APK:

```text
com.primeintellect.dummyrl
```

The app has stable resource IDs, durable `SharedPreferences`, and deterministic rewards.

## 1. Mental Model

The core loop is:

```text
Taskset
  -> Task
  -> Observation
  -> Policy/model
  -> Strict action parser
  -> Safety policy
  -> Device backend
  -> Durable app state
  -> Reward verifier
  -> Artifact writer
```

One step looks like this:

```python
observation = env.reset()
result = env.step(action)
next_observation = result.observation
reward = result.reward
done = result.done
info = result.info
```

The `info` object contains the benchmark details:

```json
{
  "task_id": "form_submit_001",
  "episode_id": "ep_form_submit_001_...",
  "step": 4,
  "backend": "adb",
  "action_valid": true,
  "reward_components": {},
  "exact_success": false,
  "apk_state": {},
  "error": null
}
```

## 2. Beginner Quickstart

Quickstart:

```bash
make test
make run
```

Expected rollout output:

```text
Rollout run completed
Run ID: ...
Backend: adb
Tasks: 4
Success rate: 1.0
Artifacts: artifacts/runs/{run_id}
Replay: artifacts/runs/{run_id}/replay.html
```

Open the replay file in a browser:

```text
artifacts/runs/{run_id}/replay.html
```

## 3. Project Map

Important paths:

```text
android_adk_rl_env/
  core/                 Shared primitives: actions, observations, reward, artifacts, safety
  devices/              Fake/ADB/AndroidWorld device boundary
  envs/                 Environment factories and compatibility modules
  policies/             Scripted, random, OpenAI, local RL, VLM policy interfaces
  tasks/                Task definitions and reward contracts
  training/             Rollout and local RL helpers

dummy_android_app/      Real Java Android APK
environments/           Prime-style environment package
prime_android_adk_rl_env/
                        Verifiers / Prime entry point
scripts/                Build, run, reset, collect-artifact commands
tests/                  Unit, integration, AndroidWorld, Prime tests
docs/                   Guides and architecture docs
artifacts/runs/         Demo and benchmark artifacts
```

## 4. Run The Test Suites

Run unit tests:

```bash
make test
```

Run integration tests:

```bash
make integration
```

The ADB integration test is skipped unless you explicitly opt in:

```bash
RUN_ADB_INTEGRATION=1 make integration
```

Run AndroidWorld smoke tests:

```bash
make android-world
```

Run Prime import smoke tests:

```bash
make prime
```

Run the legacy top-level suite:

```bash
python3 -m unittest discover -s tests
```

## 5. Test Strategy

Fast tests use local mock devices inside `tests/` so the shipped runtime stays real-ADB-first.

Use unit tests when:

- You are validating reward logic.
- You are checking action parsing.
- You are verifying environment reset behavior.

## 6. Understand The Real APK Backend

The real APK path uses:

```text
dummy_android_app/
android_adk_rl_env/adb_device.py
android_adk_rl_env/apk_env.py
android_adk_rl_env/tasks/dummy_apk.py
```

Build the APK:

```bash
make build-apk
```

Install it on a connected emulator/device:

```bash
make install-apk
```

Run the ADB-backed form task:

```bash
make adb-run
```

Run the rollout suite through ADB:

```bash
make run
```

## 7. Episode-Safe Rewards

The environment protects against stale successful app state.

Every rollout gets a unique `episode_id`:

```text
ep_form_submit_001_20260612_...
```

The APK receives this ID at launch:

```text
adb shell am start ... --es episode_id <episode_id>
```

The app writes the same ID to:

```text
shared_prefs/dummy_state.xml
```

Exact success requires:

```text
stored_episode_id == current_episode_id
query matches
name matches
email matches
submitted == true
screen == submitted
```

This is implemented in:

```text
android_adk_rl_env/tasks/dummy_apk.py
dummy_android_app/src/com/primeintellect/dummyrl/MainActivity.java
```

Tests:

```bash
python3 -m unittest tests.unit.test_reward
```

## 8. Strict Action Schema

Model-facing actions use one strict JSON shape.

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

Example:

```json
{
  "type": "type_text",
  "element_id": "name_input",
  "text": "Ada Lovelace",
  "x": null,
  "y": null,
  "x1": null,
  "y1": null,
  "x2": null,
  "y2": null,
  "duration_ms": null
}
```

Invalid actions do not crash the rollout. They return:

```json
{
  "reward": -0.05,
  "error": "invalid_action_schema"
}
```

Implementation:

```text
android_adk_rl_env/core/actions.py
android_adk_rl_env/apk_env.py
```

Tests:

```bash
python3 -m unittest tests.unit.test_actions
```

## 9. Observations

The project supports compact/full/screenshot observation styles.

Compact text observation includes:

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

Implementation:

```text
android_adk_rl_env/core/observations.py
```

Test:

```bash
python3 -m unittest tests.unit.test_observations
```

## 10. Artifacts

Rollout and benchmark runs write:

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

Implementation:

```text
android_adk_rl_env/core/artifacts.py
```

Run:

```bash
make run
```

Inspect:

```bash
ls artifacts/runs
```

## 11. Tasksets

Tasksets live in:

```text
environments/mobile_android_rl/mobile_android_rl/tasks/
```

Current files:

```text
form_train.jsonl  25 tasks
form_eval.jsonl   25 tasks
ride_train.jsonl  25 tasks
ride_eval.jsonl   25 tasks
```

Total:

```text
100 tasks
```

Load them:

```bash
PYTHONPATH=environments/mobile_android_rl python3 - <<'PY'
from mobile_android_rl import load_taskset
print(len(load_taskset(split="eval", app="form").tasks))
print(len(load_taskset(split="eval", app="ride").tasks))
PY
```

## 12. Add A New Form Task

Open:

```text
environments/mobile_android_rl/mobile_android_rl/tasks/form_eval.jsonl
```

Add one line:

```json
{"task_id":"form_submit_eval_026","app":"form","instruction":"Search bike rental, enter Test User and test@example.com, then submit.","start_screen":"home","max_steps":10,"seed":226,"expected_state":{"query":"bike rental","name":"Test User","email":"test@example.com","submitted":true},"randomization":{"button_text_variant":true,"network_delay_ms":[0,300]}}
```

Then test loading:

```bash
make test
```

## 13. Add A New Reward Rule

For the form APK, edit:

```text
android_adk_rl_env/tasks/dummy_apk.py
```

The reward flow is:

```text
state_from_prefs()
  -> reward_components_from_prefs()
  -> shaped_reward_from_prefs()
  -> reward_from_prefs()
```

When adding a new field:

1. Add the expected field to `expected_state()`.
2. Make the APK write the field into `SharedPreferences`.
3. Add unit tests in `tests/unit/test_reward.py`.
4. Run `make test`.

## 14. Add A New Device Backend

Device backends live under:

```text
android_adk_rl_env/devices/
```

The backend should implement:

```python
reset_app(episode_id)
click_resource(resource_name)
input_resource(resource_name, text)
press_back()
read_shared_prefs()
dump_resource_nodes(resource_names)
```

Then wire it in:

```text
android_adk_rl_env/envs/mobile_task_env.py
```

## 15. Docker Runner

There are two Docker paths.

Host-ADB runner:

```text
Dockerfile.runner
docker-compose.yml
```

Commands:

```bash
make docker-build
make docker-test
make docker-run
```

Full AndroidWorld/emulator image:

```text
Dockerfile
compose.yaml
docker/
```

Commands:

```bash
./scripts/docker_run.sh build
./scripts/docker_run.sh tests
OPENAI_API_KEY=... ./scripts/docker_run.sh android-world-openai
```

The full emulator path needs KVM/nested virtualization.

## 16. AndroidWorld Path

Install AndroidWorld and Android SDK/AVD:

```bash
./scripts/install_android_world.sh
```

Run OpenAI through AndroidWorld:

```bash
OPENAI_API_KEY=... make androidworld-openai
```

Backend implementation:

```text
android_adk_rl_env/android_world_bridge.py
android_adk_rl_env/android_world_runner.py
```

## 17. Prime Path

Prime/verifiers entry point:

```python
from prime_android_adk_rl_env import load_environment
```

Prime-style package:

```python
from mobile_android_rl import load_environment, load_taskset, load_harness
```

Run:

```bash
OPENAI_API_KEY=... make prime-eval
```

Config files:

```text
configs/prime_eval_dummy_apk.yaml
configs/prime_eval_ride_booking.yaml
configs/prime_train_ride_booking.yaml
```

## 18. OpenAI Policy

The OpenAI policy lives in:

```text
android_adk_rl_env/policies/openai_policy.py
```

It asks the model for one strict JSON action per turn.

Run with:

```bash
OPENAI_API_KEY=... python3 -B -m android_adk_rl_env.train \
  --task dummy_apk \
  --policy openai \
  --backend adb \
  --model gpt-4o-mini \
  --episodes 1 \
  --output artifacts/rollouts/openai_dummy_apk_rollouts.jsonl \
  --compact
```

## 19. Local RL

Train a local tabular policy:

```bash
python3 -B -m android_adk_rl_env.rl_train \
  --episodes 50 \
  --eval-episodes 5 \
  --max-steps 10 \
  --checkpoint artifacts/rl/dummy_apk_policy.json \
  --compact
```

Benchmark:

```bash
python3 -B -m android_adk_rl_env.rl_benchmark \
  --checkpoint artifacts/rl/dummy_apk_policy.json \
  --episodes 10 \
  --output artifacts/rl/dummy_apk_rl_benchmark.jsonl \
  --compact
```

## 20. Safety Policy

Safety defaults to true.

Implementation:

```text
android_adk_rl_env/core/safety.py
```

It blocks obvious destructive contexts such as:

```text
real payment
real purchase
deleting data
sending messages
changing account settings
sharing personal data
```

The current dummy apps do not perform real payments, real rides, real account changes, OTP, or personal-data workflows.

## 21. Architecture Summary

Detailed architecture lives in:

```text
docs/ARCHITECTURE.md
```

Short version:

```text
Taskset JSONL
  -> Task object
  -> Env reset
  -> Device reset
  -> Observation builder
  -> Policy
  -> Action parser
  -> Safety policy
  -> Device execution
  -> Durable state reader
  -> Reward verifier
  -> Artifact writer
```

## 22. Debugging Checklist

If unit tests fail:

```bash
make test
```

If a rollout run fails:

```bash
make run
```

If ADB fails:

```bash
adb devices
./scripts/reset_device.sh
```

If AndroidWorld is missing:

```bash
python3 -m android_adk_rl_env.android_world_runner --status
./scripts/install_android_world.sh
```

If Docker warns about multiple compose files, use the exact file:

```bash
docker compose -f docker-compose.yml config
docker compose -f compose.yaml config
```

## 23. Beginner To Smart Learning Path

Follow this sequence:

1. Run `make test`.
2. Start an emulator/device and run `make run`.
3. Open `artifacts/runs/{run_id}/replay.html`.
4. Read `android_adk_rl_env/core/actions.py`.
5. Read `android_adk_rl_env/tasks/dummy_apk.py`.
6. Read `android_adk_rl_env/apk_env.py`.
7. Add one JSONL task.
8. Add one reward test.
9. Run `make run` with an emulator.
10. Run AndroidWorld with OpenAI.
11. Run Prime eval.
12. Create a new dummy app category taskset.

That progression takes you from beginner usage to smart environment authoring.
