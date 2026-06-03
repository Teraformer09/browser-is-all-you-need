# Short Note: Prime + AndroidWorld + Android ADK Dummy APK

This repo implements a mobile Android APK RL/evaluation environment that can be run through Prime Intellect CLI, AndroidWorld, or direct ADB.

## What Is Implemented

- **Real dummy Android APK**: `com.primeintellect.dummyrl` in `dummy_android_app/`.
- **ADK-style environment loop**: `reset -> observation -> action -> step -> reward -> done`.
- **ADB backend**: installs APK, launches app, dumps UI, reads reward state, captures screenshots/video.
- **AndroidWorld backend**: uses AndroidWorld `AsyncEnv` and `JSONAction` to act on the emulator.
- **Prime Intellect/verifiers SDK package**: `prime_android_adk_rl_env.load_environment()` returns a real `verifiers.MultiTurnEnv`.
- **OpenAI model policy**: model emits JSON actions like `input_resource` and `click_resource`.
- **Reward**: computed from APK `SharedPreferences`, not from model text.

## How It Works

1. `scripts/install_android_world.sh` installs AndroidWorld, Android SDK tools, emulator, platform tools, and an API 33 AVD.
2. `scripts/build_dummy_apk.sh` builds/signs the dummy APK.
3. `scripts/install_dummy_apk.sh` installs and launches the APK on an emulator/device.
4. The model receives the current UI observation and task goal.
5. The model returns one JSON action:

```json
{"action":"input_resource","target":"search_input","text":"airport ride"}
```

6. The env executes the action through ADB or AndroidWorld.
7. The APK writes durable task state into `shared_prefs/dummy_state.xml`.
8. The reward function reads that state and checks:

```json
{"query": true, "name": true, "email": true, "submitted": true}
```

9. When all reward components are true, `final_reward = 1.0` and the rollout succeeds.

## Main Commands

Install AndroidWorld + emulator stack:

```bash
./scripts/install_android_world.sh
```

Run actual AndroidWorld + OpenAI model with screenshot/video artifacts:

```bash
./scripts/run_android_world_openai.sh
```

Run proper Prime CLI / verifiers evaluation:

```bash
./scripts/run_prime_eval_android_adk.sh
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Verified Results

- AndroidWorld + OpenAI run: `success_rate = 1.0`, `final_reward = 1.0`.
- Prime CLI eval run: `avg_reward = 1.0`, `_apk_reward = 1.0`.
- Unit tests: passing.

## Important Files

- `prime_android_adk_rl_env/prime_android_adk_rl_env.py`: Prime/verifiers environment.
- `android_adk_rl_env/android_world_bridge.py`: AndroidWorld bridge.
- `android_adk_rl_env/apk_env.py`: APK step environment.
- `android_adk_rl_env/tasks/dummy_apk.py`: task goal and reward.
- `scripts/run_prime_eval_android_adk.sh`: Prime CLI run script.
- `scripts/run_android_world_openai.sh`: AndroidWorld run script with artifacts.
