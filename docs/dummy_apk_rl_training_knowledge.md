# Dummy APK RL Training Knowledge

Last updated: 2026-06-03

This file explains how the dummy APK RL flow works from start to end in this repo.

Important clarification: this project does not contain a full neural-network training loop like PPO, GRPO, replay buffers, gradient updates, checkpoints, or distributed workers. It contains the environment/evaluation side of RL: task goal, action interface, device/app state, rollout, reward calculation, and success result. A real trainer can plug into this environment by replacing the scripted policy with a model policy.

## 0 To 100 Flow

```text
source code
  -> build dummy Android APK
  -> install APK on emulator/device
  -> launch app
  -> create task goal
  -> policy chooses actions
  -> ADB/UIAutomator executes actions on real UI
  -> app saves durable state in SharedPreferences
  -> task reads durable state
  -> reward function returns 1.0 or 0.0
  -> runner prints trajectory and final success JSON
```

## Main Files

| File | Role |
|---|---|
| `dummy_android_app/src/com/primeintellect/dummyrl/MainActivity.java` | Real Android app UI and state persistence. |
| `dummy_android_app/res/values/ids.xml` | Stable resource IDs used by UI automation. |
| `dummy_android_app/AndroidManifest.xml` | Package name and launch activity. |
| `scripts/build_dummy_apk.sh` | Builds and signs the APK without Gradle. |
| `scripts/install_dummy_apk.sh` | Installs and launches the APK on ADB device. |
| `android_adk_rl_env/adb_device.py` | ADB/UIAutomator device adapter. |
| `android_adk_rl_env/tasks/dummy_apk.py` | APK-backed task, scripted rollout, reward function. |
| `android_adk_rl_env/runner.py` | CLI entry point. Chooses task and policy. |
| `tests/test_create_note.py` | Unit tests for mock flow and dummy APK reward parsing. |

## App Behavior

The dummy app package is:

```text
com.primeintellect.dummyrl
```

The app screen contains these automation targets:

| Resource ID | Widget | Purpose |
|---|---|---|
| `search_input` | EditText | Search query. |
| `search_button` | Button | Saves/searches current query. |
| `search_result` | TextView | Displays search result text. |
| `name_input` | EditText | Form name. |
| `email_input` | EditText | Form email. |
| `submit_button` | Button | Submits the form. |
| `status_text` | TextView | Displays submitted status. |

When submit succeeds, `MainActivity.saveState(true)` writes:

```xml
<map>
    <boolean name="submitted" value="true" />
    <string name="query">airport ride</string>
    <string name="name">Ada Lovelace</string>
    <string name="email">ada@example.com</string>
</map>
```

The file lives inside app private storage:

```text
shared_prefs/dummy_state.xml
```

The reward reads it with:

```bash
adb shell run-as com.primeintellect.dummyrl cat shared_prefs/dummy_state.xml
```

## Build Step

Run:

```bash
./scripts/build_dummy_apk.sh
```

What happens internally:

1. Locate Android SDK/build tools.
2. Check `android.jar` exists.
3. Preserve the debug keystore at `dummy_android_app/debug.keystore` so rebuilds keep the same APK signature.
4. Remove and recreate `dummy_android_app/build`.
5. Run `aapt` to generate `R.java`.
6. Run `javac` to compile Java sources.
7. Run `d8` to create `classes.dex`.
8. Package resources into `dummy-unsigned.apk`.
9. Add `classes.dex` to the APK.
10. Run `zipalign`.
11. Sign with `apksigner`.
12. Verify the signed APK.
13. Output:

```text
dummy_android_app/build/out/dummy-rl-app.apk
```

## Install Step

Run:

```bash
./scripts/install_dummy_apk.sh
```

What happens internally:

1. Build the APK first if it does not exist.
2. Wait for an ADB device.
3. Install with `adb install -r`.
4. If Android reports `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, uninstall the old package and install again.
5. Launch the activity:

```bash
adb shell am start -W -S -n com.primeintellect.dummyrl/.MainActivity
```

The signature mismatch fallback matters because Android refuses to update an installed app when the package name is the same but the signing key changed.

## Run The APK-Backed RL Task

Run everything in one command:

```bash
python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk --compact
```

The runner path is:

```text
runner.py
  -> run_task("dummy_apk", "adb-scripted")
  -> DummyApkFormSearchTask()
  -> AdbDevice(package="com.primeintellect.dummyrl")
  -> task.run_scripted(device)
```

## Task Goal

`DummyApkFormSearchTask.goal` returns:

```text
In Dummy RL App, search for 'airport ride', enter name 'Ada Lovelace', enter email 'ada@example.com', and submit the form.
```

Default expected values:

| Field | Expected value |
|---|---|
| query | `airport ride` |
| name | `Ada Lovelace` |
| email | `ada@example.com` |
| submitted | `true` |

## Rollout Steps

The scripted policy performs this trajectory:

| Step | Code action | UI target | Text |
|---:|---|---|---|
| 1 | `input_resource` | `search_input` | `airport ride` |
| 2 | `click_resource` | `search_button` | |
| 3 | `input_resource` | `name_input` | `Ada Lovelace` |
| 4 | `input_resource` | `email_input` | `ada@example.com` |
| 5 | `press_back` | Android back key | |
| 6 | `click_resource` | `submit_button` | |

The returned trajectory records the five high-level task actions. `press_back()` is an implementation detail used to hide the keyboard before tapping submit.

## How ADB Actions Work

`AdbDevice.find_resource(resource_name)`:

1. Runs `adb shell uiautomator dump /sdcard/window.xml`.
2. Reads it using `adb exec-out cat /sdcard/window.xml`.
3. Parses XML with `xml.etree.ElementTree`.
4. Finds a node whose `resource-id` equals:

```text
com.primeintellect.dummyrl:id/<resource_name>
```

5. Parses node bounds such as `[0,100][300,180]`.
6. Calculates center point.

`AdbDevice.click_resource(resource_name)`:

```text
find resource -> get center x,y -> adb shell input tap x y
```

`AdbDevice.input_resource(resource_name, text)`:

```text
focus resource -> ctrl+a -> adb shell input text escaped_text
```

The focus check is important. Without it, typed text can go into the wrong field when Android focus or keyboard state changes.

## Reward Logic

`DummyApkFormSearchTask.reward_from_prefs(prefs_xml)` checks durable app state, not just screenshot text.

Reward is `1.0` only when all required strings are present:

```text
name="query">airport ride<
name="name">Ada Lovelace<
name="email">ada@example.com<
name="submitted" value="true"
```

Otherwise reward is `0.0`.

This is the RL contract:

| RL term | In this repo |
|---|---|
| Environment | Android app plus `AdbDevice`. |
| Observation | UIAutomator XML, resource IDs, final status/shared prefs. |
| Action | Resource click, resource text input, Android back key. |
| Policy | Currently `adb-scripted`; later this can be a model. |
| Reward | `reward_from_prefs()` returns `1.0` or `0.0`. |
| Done | The scripted APK task ends after the fixed trajectory and reward check. |

## Difference From The Mock Task

The repo also has a pure Python mock environment:

```bash
python3 -B -m android_adk_rl_env.runner --task create_note --policy scripted --compact
```

Mock path:

```text
AndroidAdkEnv
  -> MockAndroidDevice
  -> Action(open_app/tap/input_text/submit)
  -> CreateNoteTask.reward()
```

APK path:

```text
DummyApkFormSearchTask
  -> AdbDevice
  -> adb/uiautomator/input commands
  -> SharedPreferences reward
```

The mock path is useful for fast unit tests. The APK path proves the same idea against a real installed Android app.

## Verified In This Workspace

Commands run on 2026-06-03:

```bash
python3 -m unittest discover -s tests
```

Result:

```text
Ran 4 tests in 0.000s
OK
```

```bash
python3 -B -m android_adk_rl_env.runner --task create_note --policy scripted --compact
```

Result summary:

```json
{"task":"CreateNoteTask","success":true,"reward":1.0,"steps":6}
```

```bash
python3 -B -m compileall android_adk_rl_env tests
```

Result: Python files compiled successfully.

```bash
./scripts/build_dummy_apk.sh
```

Result: APK built at:

```text
dummy_android_app/build/out/dummy-rl-app.apk
```

```bash
python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk --compact
```

Result summary:

```json
{
  "task": "DummyApkFormSearchTask",
  "success": true,
  "reward": 1.0,
  "status_text": "Submitted: Ada Lovelace <ada@example.com>"
}
```

Final durable state observed:

```xml
<map>
    <boolean name="submitted" value="true" />
    <string name="query">airport ride</string>
    <string name="name">Ada Lovelace</string>
    <string name="email">ada@example.com</string>
</map>
```

Connected device during verification:

```text
localhost:5555 device
```

## What Is Missing For Real Training

To turn this from an RL environment demo into real RL training, add these pieces:

1. A model policy that reads observations and chooses actions.
2. A rollout collector that runs many episodes.
3. A trainer algorithm such as PPO/GRPO or another policy optimization method.
4. A dataset/log format for trajectories.
5. Checkpoint save/load.
6. Metrics for reward, success rate, episode length, invalid actions, and UI failures.
7. Parallel emulator/device management if training needs throughput.

The useful part already present is the hardest boundary for Android RL: stable UI actions plus durable reward validation.

## Common Failures

| Failure | Meaning | Fix |
|---|---|---|
| `Missing android.jar` | Android platform 34 is not installed. | Install `platforms;android-34` into `ANDROID_SDK_ROOT`. |
| `adb: no devices` | No emulator/device is connected. | Start emulator or connect device, then run `adb devices`. |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | Existing package was signed with a different key. | Current install script uninstalls/reinstalls automatically for this package. |
| `resource not found` | UIAutomator did not find the expected resource ID. | Confirm app is launched and `ids.xml`/Java IDs match task targets. |
| Reward `0.0` | SharedPreferences did not contain exact expected state. | Inspect `dummy_state.xml` and compare query/name/email/submitted values. |

## Mental Model

When you read or modify this repo, think in this order:

1. The Android app defines stable UI and durable state.
2. The task defines the goal and expected final state.
3. The device adapter converts high-level actions into ADB commands.
4. The policy produces actions.
5. The reward reads durable state and grades the episode.
6. The runner ties it together and prints the final JSON.

That is the complete dummy APK RL path from zero to success.


## Implemented Model Loop

The repo now includes a step-based APK environment and model-training support files:

| File | Role |
|---|---|
| `android_adk_rl_env/apk_env.py` | `DummyApkEnv.reset()` and `DummyApkEnv.step()` around the real APK. |
| `android_adk_rl_env/policies/scripted_policy.py` | Deterministic policy for smoke tests and demonstration data. |
| `android_adk_rl_env/policies/openai_policy.py` | OpenAI Responses API policy that emits structured JSON actions. |
| `android_adk_rl_env/training/rollout.py` | Episode collection and JSONL writing. |
| `android_adk_rl_env/train.py` | CLI for scripted or OpenAI-policy rollouts. |
| `android_adk_rl_env/openai_finetune.py` | SFT JSONL preparation plus OpenAI file upload and fine-tune job creation. |

The OpenAI policy uses Structured Outputs so the model must choose one valid action from:

```text
click_resource
input_resource
press_back
wait
finish
```

OpenAI API key is required only for these commands:

```bash
export OPENAI_API_KEY=...
python3 -B -m android_adk_rl_env.train --task dummy_apk --policy openai --model gpt-4o-mini --episodes 1
python3 -B -m android_adk_rl_env.openai_finetune submit --training-file artifacts/openai/dummy_apk_sft.jsonl --model gpt-4o-mini
```

No key is required for local tests, scripted APK rollouts, or SFT JSONL preparation.

OpenAI fine-tuning here is supervised fine-tuning from successful trajectories. The local environment still computes rewards and collects rollouts; OpenAI fine-tuning updates the model from JSONL examples after upload.


## RL-Only Training Path

The repo now has a local RL-only trainer that does not use OpenAI fine-tuning, SFT datasets, or demonstration labels.

Files:

| File | Role |
|---|---|
| `android_adk_rl_env/training/local_rl.py` | Tabular softmax policy, action candidates, policy-gradient updates, checkpoint save/load, metrics. |
| `android_adk_rl_env/rl_train.py` | Trains the local RL policy against the APK env. |
| `android_adk_rl_env/rl_benchmark.py` | Evaluates a saved RL checkpoint. |

The RL-only loop is:

```text
reset APK
  -> observe UI and reward state
  -> sample one structured Android action
  -> execute through ADB
  -> read shaped/final reward
  -> store transition
  -> compute discounted returns
  -> update policy preferences with policy gradient
  -> save checkpoint
```

The trainer uses a finite action space of structured Android actions, for example:

```json
{"action": "input_resource", "target": "search_input", "text": "airport ride"}
{"action": "click_resource", "target": "submit_button", "text": null}
{"action": "press_back", "target": null, "text": null}
```

Train:

```bash
python3 -B -m android_adk_rl_env.rl_train --episodes 50 --eval-episodes 5 --max-steps 10 --checkpoint artifacts/rl/dummy_apk_policy.json --compact
```

Benchmark:

```bash
python3 -B -m android_adk_rl_env.rl_benchmark --checkpoint artifacts/rl/dummy_apk_policy.json --episodes 10 --compact
```

This is true reward-based RL for the local policy. It is not OpenAI model training. To RL-train an OpenAI hosted model, the equivalent would be OpenAI RFT, which is a hosted training product. This local path avoids that and trains only the repo-local policy checkpoint.
