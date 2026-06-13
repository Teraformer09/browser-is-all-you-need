# Prime Intellect Mobile Android ADK RL Environment

This repo is a real Android RL and evaluation environment built around the APK `com.primeintellect.dummyrl`.

The environment supports:

- Real ADB-backed execution
- Strict JSON mobile actions
- Reward verification from durable app state
- Form and ride-booking dummy tasks
- Rollout artifacts in `artifacts/runs/`
- Prime-compatible environment loading
- Docker runner image for local execution

## Verified On 2026-06-13

These paths were run successfully against a real emulator:

- `make build-apk`
- `make install-apk`
- `ADB_SERIAL=emulator-5558 make adb-run`
- `ADB_SERIAL=emulator-5558 make run`
- `make test`
- `python3 -m unittest discover -s tests`
- `docker compose -f docker-compose.yml build mobile-rl-runner`

Verified rollout result:

```text
Rollout run completed
Run ID: 20260613_120253
Backend: adb
Tasks: 4
Success rate: 1.0
Artifacts: artifacts/runs/20260613_120253
Replay: artifacts/runs/20260613_120253/replay.html
```

## Quick Start

Run unit tests:

```bash
make test
python3 -m unittest discover -s tests
```

Build and install the APK on the current ADB target:

```bash
make build-apk
make install-apk
```

Run the single-task scripted ADB check:

```bash
ADB_SERIAL=emulator-5558 make adb-run
```

Run the full real rollout suite:

```bash
ADB_SERIAL=emulator-5558 make run
```

## Emulator Setup

List devices:

```bash
adb devices -l
```

Healthcheck a chosen emulator:

```bash
ADB_SERIAL=emulator-5558 ./scripts/adb_healthcheck.sh
```

If you need a clean emulator, the repo works well with an API 34 AVD. Example:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_SDK_ROOT=/data/Balram/android-sdk
export ANDROID_AVD_HOME=$PWD/.deps/android_avd

yes | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager \
  --sdk_root=$ANDROID_SDK_ROOT \
  "build-tools;34.0.0" \
  "platforms;android-34" \
  "system-images;android-34;google_apis;x86_64"

printf 'no\n' | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager create avd \
  -n AndroidWorld_API_34 \
  -k "system-images;android-34;google_apis;x86_64" \
  --device pixel_6

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

## OpenAI And Prime

These paths are implemented, but were not executed in this session because `OPENAI_API_KEY` was not available:

```bash
OPENAI_API_KEY=... python3 -B -m android_adk_rl_env.train \
  --task dummy_apk \
  --policy openai \
  --backend adb \
  --episodes 1 \
  --model gpt-4o-mini \
  --output artifacts/rollouts/openai_dummy_apk_rollouts.jsonl \
  --compact
```

```bash
OPENAI_API_KEY=... ./scripts/run_prime_eval_android_adk.sh
```

## Main Files

- `android_adk_rl_env/adb_device.py`: ADB device control and UI/state access
- `android_adk_rl_env/apk_env.py`: step-based APK environment
- `android_adk_rl_env/rollout_runner.py`: real rollout suite
- `android_adk_rl_env/tasks/dummy_apk.py`: form task and reward verification
- `android_adk_rl_env/tasks/ride_booking.py`: ride task and reward verification
- `scripts/build_dummy_apk.sh`: APK build/sign path
- `scripts/install_dummy_apk.sh`: APK install/launch path
- `scripts/run_rollout.sh`: real rollout entrypoint

## Docs

- [IMPLEMENTED_AND_WORKING.md](IMPLEMENTED_AND_WORKING.md)
- [docs/COMPLETE_TUTORIAL.md](docs/COMPLETE_TUTORIAL.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
