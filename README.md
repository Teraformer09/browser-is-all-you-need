# Prime Intellect Mobile Android ADK RL Environment

This repo is a real Android APK/ADK-style RL and evaluation environment. The reference app is `com.primeintellect.dummyrl`, controlled through ADB or AndroidWorld, with reward read from durable app state.

## Go-Live Branch Status

The `go-live-e2e-hardening` branch adds the end-to-end rollout scaffold from the Mobile Android RL requirement document:

- Episode-safe rewards with per-rollout `episode_id`.
- Strict model action schema and non-crashing invalid-action handling.
- Reset lifecycle for ADB rollouts.
- Unit/integration/AndroidWorld/Prime test split.
- 100 JSONL tasks across form and ride train/eval tasksets.
- Prime package folder at `environments/mobile_android_rl/`.
- Host-ADB Docker runner plus full AndroidWorld Docker image.
- `make run` rollout execution with standardized artifacts and `replay.html`.
- Safety policy enabled by default.

Fastest local check:

```bash
make test
```

Real run:

```bash
make run
```

## Learning Path

Start here if you are new to the project:

- [Complete Tutorial](docs/COMPLETE_TUTORIAL.md): how to run, extend, and debug the environment.
- [Architecture Guide](docs/ARCHITECTURE.md): runtime layers, device flow, rewards, artifacts, and extension points.

The current end-to-end path is:

```text
install AndroidWorld + Android SDK/AVD
  -> build dummy APK
  -> boot Android emulator with AndroidWorld gRPC
  -> install APK through ADB
  -> run OpenAI model policy
  -> execute AndroidWorld JSONAction steps
  -> read APK SharedPreferences reward
  -> write rollout, benchmark summary, screenshot, and video artifacts
```

## Requirement Fit

This infra is aimed at mobile Android apps, not web/browser tasks.

| Requirement | Current support |
|---|---|
| Mobile Android APK app | Yes. Reference APK lives in `dummy_android_app/`. |
| ADK-style environment boundary | Yes. Structured actions, reset/step loop, observations, rewards, rollout JSONL. |
| AndroidWorld backend | Yes. `android_adk_rl_env/android_world_bridge.py` maps actions to AndroidWorld `JSONAction`. |
| ADB integration | Yes. Build, install, launch, UI dump, SharedPreferences reward, screenshot, video. |
| Model policy | Yes. OpenAI Responses API policy via `.env` `OPENAI_API_KEY`. |
| RL reward | Yes. Reward comes from APK durable state, not from model text. |
| Benchmark artifacts | Yes. JSONL rollout, summary JSON, PNG screenshot, MP4 video, emulator logs. |
| Prime Intellect-style format | Yes for rollout/summary/media artifact shape. If Prime Intellect gives a stricter schema, only the serializer/manifest layer should need adjustment. |

## Quick Start: Actual AndroidWorld + OpenAI Run

Put your key in `.env`:

```bash
OPENAI_API_KEY=...
```

Install AndroidWorld, Android SDK packages, emulator, and the API 33 AVD:

```bash
./scripts/install_android_world.sh
```

Run one actual model episode against the dummy APK through AndroidWorld:

```bash
./scripts/run_android_world_openai.sh
```

Default output:

```text
artifacts/android_world_openai_run/
  rollout.jsonl       # Prime-style episode trajectory/reward data
  summary.json        # benchmark summary and artifact pointers
  final_screen.png    # final emulator screenshot
  emulator_run.mp4    # screen recording
  emulator.log        # emulator boot/gRPC log
  screenrecord.log    # Android screenrecord log
  result.json         # compact runner result
```

A verified run on this branch completed with:

```json
{
  "backend": "android_world",
  "policy": "openai",
  "model": "gpt-4o-mini",
  "success_rate": 1.0,
  "final_reward": 1.0,
  "steps": 9
}
```

## Docker Quick Start

The repo includes a full Docker image and Compose runner for the Android SDK, emulator, AndroidWorld, Prime CLI, verifiers, and the dummy APK toolchain.

Build and run the local test suite:

```bash
./scripts/docker_run.sh build
./scripts/docker_run.sh tests
```

Run AndroidWorld + OpenAI inside Docker:

```bash
OPENAI_API_KEY=... ./scripts/docker_run.sh android-world-openai
```

Run the Prime/verifiers eval inside Docker:

```bash
OPENAI_API_KEY=... ./scripts/docker_run.sh prime-eval
```

## Dummy APK Task

The dummy app is intentionally small but follows the same contract expected from larger Uber-like, DoorDash-like, shopping, or booking dummy apps:

```text
stable Android resource IDs
  -> model/agent actions target resource IDs
  -> app writes task state to SharedPreferences
  -> environment reads durable state through ADB
  -> reward function grades exact expected state
```

Current goal:

```text
Search for 'airport ride', enter name 'Ada Lovelace', enter email 'ada@example.com', and submit the form.
```

Success requires all reward components:

```json
{
  "query": true,
  "name": true,
  "email": true,
  "submitted": true
}
```

## Local Commands

Run unit tests:

```bash
python3 -m unittest discover -s tests
```

Build/install only the APK against the current ADB device:

```bash
./scripts/build_dummy_apk.sh
./scripts/install_dummy_apk.sh
```

Run the ADB-backed scripted APK task:

```bash
python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk --compact
```

Collect APK rollouts without AndroidWorld:

```bash
python3 -B -m android_adk_rl_env.train --task dummy_apk --policy openai --model gpt-4o-mini --episodes 1 --output artifacts/rollouts/openai_dummy_apk_rollouts.jsonl --compact
```

Train/evaluate the local RL-only tabular policy against the APK environment:

```bash
python3 -B -m android_adk_rl_env.rl_train --episodes 50 --eval-episodes 5 --max-steps 10 --checkpoint artifacts/rl/dummy_apk_policy.json --compact
python3 -B -m android_adk_rl_env.rl_benchmark --checkpoint artifacts/rl/dummy_apk_policy.json --episodes 10 --output artifacts/rl/dummy_apk_rl_benchmark.jsonl --compact
```


## Prime CLI / Verifiers Environment

This repo now exposes the official Prime/verifiers entry point:

```python
from prime_android_adk_rl_env import load_environment
```

Run a local Prime CLI eval against the real dummy APK:

```bash
./scripts/run_prime_eval_android_adk.sh
```

The verified Prime eval result used `gpt-4o-mini` through `https://api.openai.com/v1` and returned reward `1.0` with `_apk_reward: 1.0`.

## Project Layout

```text
android_adk_rl_env/
  adb_device.py              # ADB helper with serial targeting
  apk_env.py                 # step-based real APK environment
  android_world_bridge.py    # AndroidWorld AsyncEnv/JSONAction bridge
  android_world_runner.py    # AndroidWorld/ADB rollout runner
  policies/openai_policy.py  # OpenAI model action policy
  tasks/dummy_apk.py         # dummy APK task and reward function
  training/rollout.py        # rollout collection and JSONL writer
dummy_android_app/           # real Java Android dummy APK
scripts/
  install_android_world.sh   # installs AndroidWorld + SDK/AVD dependencies
  run_android_world_openai.sh # actual AndroidWorld + OpenAI run with artifacts
  build_dummy_apk.sh         # builds/signs APK without Gradle
  install_dummy_apk.sh       # installs/launches APK through ADB
docs/
  COMPLETE_TUTORIAL.md
  ARCHITECTURE.md
```

## Notes

The OpenAI fine-tuning helpers are still present for optional supervised-data workflows, but the AndroidWorld run path above is RL/evaluation only: the model acts in the environment, the APK state produces reward, and no model fine-tuning job is submitted.
