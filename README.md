# Prime Intellect Android ADK RL Environment

This repository is a real mobile Android RL and evaluation environment built around the APK `com.primeintellect.dummyrl`.

It is now organized as an RL-first codebase:

- real APK execution through `adb`
- optional AndroidWorld execution for the interaction layer
- rollout collection and benchmark artifact generation
- local RL training and RL benchmarking
- Prime-compatible environment loading and eval entrypoints
- no SFT pipeline in this branch

## What Happens In A Run

The runtime loop is:

```text
Task
  -> Environment reset
  -> Observation
  -> Policy or model
  -> Strict JSON action
  -> Device execution
  -> Durable APK state read
  -> Reward calculation
  -> Artifact write
```

For one environment step:

```python
observation = env.reset()
result = env.step(action)
next_observation = result.observation
reward = result.reward
done = result.done
info = result.info
```

The reward comes from durable app state written by the APK, not from guessed UI heuristics.

## Repo Structure

Main directories:

```text
android_adk_rl_env/
  adb_device.py              Real device control
  apk_env.py                 Step-based APK RL environment
  android_world_bridge.py    AndroidWorld-backed environment bridge
  android_world_runner.py    AndroidWorld rollout runner
  train.py                   OpenAI rollout collection
  rl_train.py                Local RL training entrypoint
  rl_benchmark.py            Local RL benchmark entrypoint
  rollout_runner.py          Multi-task rollout and artifact generation
  core/                      Actions, observations, reward, artifacts, safety, metrics
  policies/                  Scripted, OpenAI, random, local RL policy code
  tasks/                     Form and ride task definitions
  training/                  Rollout and local RL helpers

dummy_android_app/           Real Android app source
prime_android_adk_rl_env/    Prime environment loader and eval bridge
scripts/                     Build, install, run, AndroidWorld, Prime, Docker helpers
tests/                       Unit and integration tests
docs/                        Tutorial and architecture notes
artifacts/                   Run outputs
```

## Main Runtime Paths

### 1. Unit Tests

Fast local verification:

```bash
make test
python3 -m unittest discover -s tests
```

Validated locally on `2026-06-13`:

```text
make test: passing
python3 -m unittest discover -s tests: passing
Skipped: 1 test
```

### 2. Real ADB Rollout

This is the main stable path in the repo.

Build and install the APK:

```bash
make build-apk
make install-apk
```

Check the connected emulator or device:

```bash
adb devices -l
ADB_SERIAL=emulator-5558 ./scripts/adb_healthcheck.sh
```

Run one scripted task:

```bash
ADB_SERIAL=emulator-5558 make adb-run
```

Run the full rollout suite:

```bash
ADB_SERIAL=emulator-5558 make run
```

Validated locally on `2026-06-13`:

```text
Rollout run completed
Run ID: 20260613_120253
Backend: adb
Tasks: 4
Success rate: 1.0
Artifacts: artifacts/runs/20260613_120253
Replay: artifacts/runs/20260613_120253/replay.html
```

### 3. OpenAI Rollout Collection

Use the OpenAI policy against the APK environment:

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

This path uses:

- strict JSON actions
- observation compaction
- reward verification from APK state
- rollout JSONL output for later analysis

### 3.1 Proof Benchmark Run (Real ADB, Repeatability)

Run the proof benchmark with repeated attempts per task family:

```bash
./scripts/run_proof_benchmark.sh \
  --backend adb \
  --policy scripted \
  --attempts-per-instance 20 \
  --pass-k 1 2 5 10 \
  --bootstrap-samples 1000 \
  --output artifacts/benchmarks/proof
```

This writes:

- `summary.json` with benchmark metadata
- `task_results.jsonl` with per-attempt outcomes
- `metrics.json` with averaged success and step metrics
- `pass_at_k.json` with `pass@k`, `safe_pass@k`, and reliability (`reliable@k`, `safe_reliable@k`)
- `confidence_intervals.json` when `--bootstrap-samples` is set to a positive value

Make targets:

```bash
make benchmark-quick
make benchmark-proof
make benchmark-release
```

### 4. Local RL Training

Train a local tabular policy:

```bash
python3 -B -m android_adk_rl_env.rl_train \
  --episodes 50 \
  --eval-episodes 5 \
  --max-steps 10 \
  --checkpoint artifacts/rl/dummy_apk_policy.json \
  --compact
```

Benchmark a saved policy:

```bash
python3 -B -m android_adk_rl_env.rl_benchmark \
  --checkpoint artifacts/rl/dummy_apk_policy.json \
  --episodes 10 \
  --output artifacts/rl/dummy_apk_rl_benchmark.jsonl \
  --compact
```

### 5. AndroidWorld Run

AndroidWorld is supported as an interaction backend.

Status in this branch:

- integrated in code
- real runs were executed
- still less stable than the plain ADB path

Run it with:

```bash
ANDROID_WORLD_A11Y_METHOD=uiautomator \
ANDROID_WORLD_AVD_NAME=AndroidWorld_API_34 \
CONSOLE_PORT=5558 \
GRPC_PORT=8558 \
ADB_SERIAL=emulator-5558 \
STOP_EMULATOR_AFTER_RUN=1 \
./scripts/run_android_world_openai.sh
```

Notes:

- AndroidWorld is used for observation and action execution.
- ADB is still used for APK install/reset and reading durable app state for reward.
- `uiautomator` mode is currently the more stable AndroidWorld observation path in this repo.

### 6. Prime Eval

Prime is supported through `prime_android_adk_rl_env`.

Default Prime backend:

```text
adb
```

Run Prime eval on the stable ADB path:

```bash
OPENAI_API_KEY=... ./scripts/run_prime_eval_android_adk.sh
```

Run Prime eval with AndroidWorld explicitly enabled:

```bash
PRIME_ANDROID_BACKEND=android_world \
ANDROID_WORLD_A11Y_METHOD=uiautomator \
ANDROID_WORLD_AVD_NAME=AndroidWorld_API_34 \
CONSOLE_PORT=5558 \
GRPC_PORT=8558 \
ADB_SERIAL=emulator-5558 \
START_EMULATOR=1 \
STOP_EMULATOR_AFTER_RUN=1 \
./scripts/run_prime_eval_android_adk.sh
```

Current status:

- Prime interface and environment loading work
- Prime with `adb` is the safer path
- Prime with `android_world` is wired, but AndroidWorld runtime stability still needs hardening

## Artifacts

Real rollout runs write artifacts under `artifacts/runs/<run_id>/`.

Typical files:

```text
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

AndroidWorld runs write under `artifacts/android_world_openai_run/`.

Prime eval writes under `artifacts/prime_eval_android_adk/`.

## Emulator Setup

Recommended local setup:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_AVD_HOME=$PWD/.deps/android_avd
```

Create an API 34 emulator image:

```bash
yes | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager \
  --sdk_root=$ANDROID_SDK_ROOT \
  "build-tools;34.0.0" \
  "platforms;android-34" \
  "system-images;android-34;google_apis;x86_64"

printf 'no\n' | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager create avd \
  -n AndroidWorld_API_34 \
  -k "system-images;android-34;google_apis;x86_64" \
  --device pixel_6
```

Start it manually:

```bash
$ANDROID_SDK_ROOT/emulator/emulator \
  -avd AndroidWorld_API_34 \
  -no-window \
  -no-audio \
  -no-boot-anim \
  -gpu swiftshader_indirect \
  -no-snapshot \
  -grpc 8558 \
  -ports 5558,5559
```

## What Is Verified And What Is Not

Verified locally on `2026-06-13`:

- `make build-apk`
- `make install-apk`
- `ADB_SERIAL=emulator-5558 make adb-run`
- `ADB_SERIAL=emulator-5558 make run`
- `make test`
- `python3 -m unittest discover -s tests`
- `docker compose -f docker-compose.yml build mobile-rl-runner`

Implemented in code but not yet a fully stable claim:

- AndroidWorld OpenAI run as a universally reliable benchmark path
- Prime eval over AndroidWorld as a fully hardened path
- universal compatibility with arbitrary models without policy tuning

## Important Files

- [android_adk_rl_env/apk_env.py](android_adk_rl_env/apk_env.py)
- [android_adk_rl_env/adb_device.py](android_adk_rl_env/adb_device.py)
- [android_adk_rl_env/android_world_bridge.py](android_adk_rl_env/android_world_bridge.py)
- [android_adk_rl_env/rollout_runner.py](android_adk_rl_env/rollout_runner.py)
- [android_adk_rl_env/tasks/dummy_apk.py](android_adk_rl_env/tasks/dummy_apk.py)
- [android_adk_rl_env/rl_train.py](android_adk_rl_env/rl_train.py)
- [android_adk_rl_env/rl_benchmark.py](android_adk_rl_env/rl_benchmark.py)
- [prime_android_adk_rl_env/prime_android_adk_rl_env.py](prime_android_adk_rl_env/prime_android_adk_rl_env.py)

## More Docs

- [IMPLEMENTED_AND_WORKING.md](IMPLEMENTED_AND_WORKING.md)
- [docs/COMPLETE_TUTORIAL.md](docs/COMPLETE_TUTORIAL.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
