# AndroidWorld Integration

Last updated: 2026-06-03

This branch implements a real AndroidWorld backend for the dummy APK RL environment. It is designed for mobile Android APK/ADK-style environments where an agent acts on a live emulator and reward is computed from durable app state.

## What Is Implemented

| File | Purpose |
|---|---|
| `scripts/install_android_world.sh` | Installs repo venv dependencies, AndroidWorld, Android SDK packages, emulator, API 33 system image, and repo-local AVD. |
| `scripts/run_android_world_openai.sh` | Boots the AndroidWorld AVD with gRPC, builds/installs the dummy APK, runs one OpenAI model episode, and saves rollout/screenshot/video artifacts. |
| `android_adk_rl_env/android_world_bridge.py` | Bridge from repo `ApkAction` / reward API to AndroidWorld `AsyncEnv` and `JSONAction`. |
| `android_adk_rl_env/android_world_runner.py` | CLI runner with `--backend android_world` and `--backend adb`. |
| `tests/test_android_world_bridge.py` | Fake AndroidWorld tests for action mapping and backend observations. |

## Runtime Contract

```text
OpenAI policy emits structured action
  -> AndroidWorld executes JSONAction on emulator
  -> dummy APK changes durable SharedPreferences state
  -> ADB reads SharedPreferences
  -> reward_from_prefs / shaped_reward_from_prefs grades task
  -> rollout JSONL and summary JSON are written
```

The AndroidWorld backend and ADB backend use the same reward contract.

## Install

Use the repo script; it installs the dependency stack into local paths instead of requiring a manual Android Studio setup:

```bash
./scripts/install_android_world.sh
```

Defaults:

```text
SDK root: /data/Balram/android-sdk
AVD home: .deps/android_avd
AVD name: AndroidWorld_API_33
System image: system-images;android-33;google_apis;x86_64
```

Environment overrides are supported:

```bash
ANDROID_SDK_ROOT=/path/to/sdk ANDROID_WORLD_AVD_NAME=AndroidWorld_API_33 ./scripts/install_android_world.sh
```

## Run Actual AndroidWorld + OpenAI

Put the key in `.env`:

```bash
OPENAI_API_KEY=...
```

Run:

```bash
./scripts/run_android_world_openai.sh
```

The script uses:

```text
backend: android_world
policy: openai
model: gpt-4o-mini by default
console port: 5556
ADB serial: emulator-5556
gRPC port: 8554
```

Artifacts are written to:

```text
artifacts/android_world_openai_run/
  rollout.jsonl
  summary.json
  final_screen.png
  emulator_run.mp4
  result.json
  emulator.log
  screenrecord.log
```

## Verified Result

The latest verified run completed with:

```json
{
  "run_status": 0,
  "backend": "android_world",
  "policy": "openai",
  "model": "gpt-4o-mini",
  "success_rate": 1.0,
  "final_reward": 1.0,
  "steps": 9
}
```

The final reward components were all true:

```json
{
  "query": true,
  "name": true,
  "email": true,
  "submitted": true
}
```

## Action Mapping

Repo action:

```json
{"action": "click_resource", "target": "submit_button", "text": null}
```

AndroidWorld action:

```python
JSONAction(action_type=CLICK, index=<ui_element_index>)
```

Repo action:

```json
{"action": "input_resource", "target": "name_input", "text": "Ada Lovelace"}
```

AndroidWorld action:

```python
JSONAction(action_type=INPUT_TEXT, index=<ui_element_index>, text="Ada Lovelace", clear_text=True)
```

The bridge accepts both local IDs and full Android resource IDs, for example:

```text
name_input
com.primeintellect.dummyrl:id/name_input
```

## Prime Intellect Fit

The current artifact set is Prime Intellect-style rather than a hardcoded external schema:

```text
rollout JSONL: per-episode transitions, observations, actions, rewards
summary JSON: benchmark status, reward, success, artifact paths
media: final screenshot and emulator video
logs: emulator and screenrecord diagnostics
```

If Prime Intellect sends a stricter manifest/schema, keep the environment and AndroidWorld bridge as-is and adapt only the output serializer/manifest layer.

## Source

AndroidWorld upstream repository: https://github.com/google-research/android_world
