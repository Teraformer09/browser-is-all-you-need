# AndroidWorld Integration

Last updated: 2026-06-03

This branch adds an optional AndroidWorld backend for the dummy APK RL environment.

AndroidWorld is an Android benchmark/environment for autonomous agents. Its README describes a live Android emulator setup, durable reward signals, and custom agents that subclass `EnvironmentInteractingAgent` and act through an `AndroidEnv` / `JSONAction` interface.

## What Is Implemented

| File | Purpose |
|---|---|
| `android_adk_rl_env/android_world_bridge.py` | Optional bridge from this repo's `ApkAction` / reward API to AndroidWorld `AsyncEnv` and `JSONAction`. |
| `android_adk_rl_env/android_world_runner.py` | CLI runner with `--backend android_world` and `--backend adb`. |
| `tests/test_android_world_bridge.py` | Fake AndroidWorld tests that verify action mapping and backend observations without installing AndroidWorld. |

The bridge keeps reward validation in this repo:

```text
AndroidWorld AsyncEnv executes action
  -> dummy APK changes state
  -> SharedPreferences is read through ADB
  -> reward_from_prefs / shaped_reward_from_prefs grades the task
```

This means the AndroidWorld backend and the ADB backend use the same reward contract.

## Install AndroidWorld

AndroidWorld is not vendored into this repo. Install it separately:

```bash
git clone https://github.com/google-research/android_world.git
cd android_world
pip install -r requirements.txt
python setup.py install
```

AndroidWorld expects a live emulator. The upstream README recommends a Pixel 6 AVD with API 33 named `AndroidWorldAvd`, launched with a gRPC port:

```bash
~/Android/Sdk/emulator/emulator -avd AndroidWorldAvd -no-snapshot -grpc 8554
```

## Check Availability

From this repo:

```bash
python3 -B -m android_adk_rl_env.android_world_runner --status
```

Example when missing:

```json
{"installed": false, "reason": "ModuleNotFoundError: No module named 'android_world'"}
```

## Run With AndroidWorld Backend

Build/install the dummy APK, then run one scripted rollout through AndroidWorld:

```bash
python3 -B -m android_adk_rl_env.android_world_runner   --backend android_world   --policy scripted   --episodes 1   --install-apk   --output artifacts/android_world/scripted_rollout.jsonl   --compact
```

Use OpenAI as the policy while AndroidWorld executes Android actions:

```bash
python3 -B -m android_adk_rl_env.android_world_runner   --backend android_world   --policy openai   --model gpt-4o-mini   --episodes 1   --output artifacts/android_world/openai_rollout.jsonl   --compact
```

The OpenAI key can be loaded from `.env` as `OPENAI_API_KEY=...`.

## Fallback ADB Backend

The same runner can still use the existing local ADB backend:

```bash
python3 -B -m android_adk_rl_env.android_world_runner   --backend adb   --policy scripted   --episodes 1   --output artifacts/android_world/adb_rollout.jsonl   --compact
```

## How Actions Are Mapped

This repo action:

```json
{"action": "click_resource", "target": "submit_button", "text": null}
```

is mapped to AndroidWorld:

```python
JSONAction(action_type=CLICK, index=<ui_element_index>)
```

This repo action:

```json
{"action": "input_resource", "target": "name_input", "text": "Ada Lovelace"}
```

is mapped to AndroidWorld:

```python
JSONAction(action_type=INPUT_TEXT, index=<ui_element_index>, text="Ada Lovelace", clear_text=True)
```

The bridge finds the `index` by matching AndroidWorld UI elements against resource IDs like:

```text
com.primeintellect.dummyrl:id/name_input
```

## Current Limitations

This branch is an integration layer, not a vendored AndroidWorld fork.

Known constraints:

```text
AndroidWorld must be installed separately.
The AndroidWorld emulator must be launched with its expected gRPC setup.
The dummy APK still provides reward through SharedPreferences.
The local RL-only trainer still trains a repo-local policy, not AndroidWorld's built-in agents.
```

## Sources

AndroidWorld upstream repository: https://github.com/google-research/android_world
