# Dummy APK RL Environment

Last updated: 2026-06-03

## Goal

This project now proves the target workflow:

```text
build a minimal Android APK
  -> install it on a connected Android device/emulator
  -> run an RL-style task against the real app UI
  -> click buttons and fill fields through ADB/UIAutomator
  -> validate durable app state
  -> return reward
```

The demo app is intentionally small so it can be used as the template for later demo apps such as ride booking, delivery, or shopping flows.

## App

APK package:

```text
com.primeintellect.dummyrl
```

Source:

```text
dummy_android_app/
  AndroidManifest.xml
  res/values/ids.xml
  res/values/styles.xml
  src/com/primeintellect/dummyrl/MainActivity.java
```

The app has one screen:

| Resource ID | UI element | Purpose |
|---|---|---|
| `search_input` | EditText | Search query field |
| `search_button` | Button | Runs the search |
| `search_result` | TextView | Shows the search result |
| `name_input` | EditText | Form name field |
| `email_input` | EditText | Form email field |
| `submit_button` | Button | Submits the form |
| `status_text` | TextView | Shows final status |

On submit, the app writes durable state to SharedPreferences:

```text
shared_prefs/dummy_state.xml
```

The reward function reads this file with:

```bash
adb shell run-as com.primeintellect.dummyrl cat shared_prefs/dummy_state.xml
```

## Build

This project does not use Gradle. The APK is built directly with Android SDK tools:

- `aapt`
- `javac`
- `d8`
- `zip`
- `zipalign`
- `apksigner`
- `keytool`

Build:

```bash
cd /data/Balram/prime-intellect-android-adk-rl-environments
./scripts/build_dummy_apk.sh
```

Output:

```text
dummy_android_app/build/out/dummy-rl-app.apk
```

If `android.jar` is missing, install the Android 34 platform into the writable workspace SDK root:

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sdkmanager --sdk_root=/data/Balram/android-sdk "platforms;android-34"
```

## Install And Launch

```bash
./scripts/install_dummy_apk.sh
```

The script installs the APK and launches:

```text
com.primeintellect.dummyrl/.MainActivity
```

It uses explicit `am start` instead of `monkey` because `am start` reliably brings the dummy app to the foreground:

```bash
adb shell am start -W -S -n com.primeintellect.dummyrl/.MainActivity
```

## RL Task

Task:

```text
DummyApkFormSearchTask
```

Run:

```bash
python3 -B -m android_adk_rl_env.runner   --task dummy_apk   --policy adb-scripted   --compact
```

One-command build/install/run:

```bash
python3 -B -m android_adk_rl_env.runner   --task dummy_apk   --policy adb-scripted   --install-apk   --compact
```

Expected success fields:

```json
{
  "task": "DummyApkFormSearchTask",
  "success": true,
  "reward": 1.0,
  "status_text": "Submitted: Ada Lovelace <ada@example.com>"
}
```

## How The RL Loop Works

The APK-backed path uses these files:

```text
android_adk_rl_env/adb_device.py
android_adk_rl_env/tasks/dummy_apk.py
android_adk_rl_env/runner.py
```

Flow:

```text
runner
  -> DummyApkFormSearchTask
  -> AdbDevice
  -> adb shell am start
  -> adb shell uiautomator dump
  -> parse resource IDs and bounds
  -> adb shell input tap
  -> adb shell input text
  -> adb shell run-as ... cat shared_prefs/dummy_state.xml
  -> reward_from_prefs()
```

The task performs these actions:

| Step | Action | Target | Text |
|---:|---|---|---|
| 1 | `input_resource` | `search_input` | `airport ride` |
| 2 | `click_resource` | `search_button` | |
| 3 | `input_resource` | `name_input` | `Ada Lovelace` |
| 4 | `input_resource` | `email_input` | `ada@example.com` |
| 5 | `click_resource` | `submit_button` | |

`AdbDevice.input_resource()` verifies focus before typing. This matters because Android soft-keyboard and focus behavior can otherwise send text to the previously focused field.

## Reward

The reward is durable, not screenshot-only.

Success requires all of these values in `dummy_state.xml`:

```xml
<boolean name="submitted" value="true" />
<string name="query">airport ride</string>
<string name="name">Ada Lovelace</string>
<string name="email">ada@example.com</string>
```

Reward logic:

```text
reward = 1.0 if query, name, email, and submitted=true match
reward = 0.0 otherwise
```

## Why This Matters

This proves the minimal APK-backed RL pattern:

```text
custom APK
+ stable resource IDs
+ ADB/UIAutomator action layer
+ durable state reward
+ CLI runner
+ repeatable install/run script
```

The same structure can be reused for future demo apps:

- Uber-like app: pickup, destination, ride type, confirm.
- DoorDash-like app: search restaurant, add item, checkout mock order.
- Amazon-like app: search item, add to cart, validate cart state.

For those apps, keep the same pattern:

1. Give every important field/button a stable resource ID.
2. Store final task state in durable app storage.
3. Validate through storage or an explicit app API, not only screen text.
4. Keep task actions resource-based, with coordinate fallback only when necessary.
