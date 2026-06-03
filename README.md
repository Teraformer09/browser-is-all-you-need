# Prime Intellect Android ADK RL Environment

This project is a runnable AndroidWorld-inspired environment scaffold for Android ADK-style RL/evaluation work.

It includes one working task:

```text
CreateNoteTask
```

The task simulates a native Android notes app. An agent must use Android-style actions to create a note with the requested title and body. The environment returns reward `1.0` only when the durable app state contains the expected note.

## Run The Task

From this folder:

```bash
python3 -m android_adk_rl_env.runner --task create_note --policy scripted
```

Run the real APK-backed task after building and installing the dummy app:

```bash
./scripts/build_dummy_apk.sh
./scripts/install_dummy_apk.sh
python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted
```

Or build, install, and run in one command:

```bash
python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk
```

Expected result:

```json
{
  "task": "CreateNoteTask",
  "success": true,
  "reward": 1.0
}
```

## Run Tests

```bash
python3 -m unittest discover -s tests
```

## Project Layout

```text
android_adk_rl_env/
  actions.py          # action schema
  env.py              # environment loop and mock Android device
  runner.py           # CLI runner
  tasks/
    base.py           # task protocol
    create_note.py    # one runnable task
configs/
  eval/smoke.toml     # sample eval config
tests/
  test_create_note.py # task tests
docs/
  dummy_apk_rl_env.md # APK-backed RL implementation notes
dummy_android_app/    # minimal Java Android APK
scripts/              # direct APK build/install scripts
requiremnt.md         # requirements
codex.md              # AI-agent context
solutation.md         # solution write-up
```

## Why A Mock Android Device?

The workspace does not include Android SDK, an emulator, AndroidWorld, or Prime CLI credentials. This scaffold therefore provides a deterministic local task that runs now while preserving the AndroidWorld task shape:

```text
Task goal -> initialize app/device state -> agent actions -> durable validator -> reward
```

The mock device boundary is intentionally narrow. To connect this to real AndroidWorld later, replace `MockAndroidDevice` with an ADB/AndroidWorld-backed controller and keep the task/reward contract.

## APK-Backed Demo

See [docs/dummy_apk_rl_env.md](docs/dummy_apk_rl_env.md) for the implementation details.


## Model Rollouts And OpenAI Fine-Tuning

Collect step-by-step APK rollouts with the scripted policy:

```bash
python3 -B -m android_adk_rl_env.train --task dummy_apk --policy scripted --episodes 1 --output artifacts/rollouts/dummy_apk_rollouts.jsonl --compact
```

Use OpenAI as the action policy by setting an API key:

```bash
export OPENAI_API_KEY=...
python3 -B -m android_adk_rl_env.train --task dummy_apk --policy openai --model gpt-4o-mini --episodes 1 --output artifacts/rollouts/openai_dummy_apk_rollouts.jsonl --compact
```

Prepare supervised fine-tuning JSONL from successful rollouts:

```bash
python3 -B -m android_adk_rl_env.openai_finetune prepare --rollouts artifacts/rollouts/dummy_apk_rollouts.jsonl --output artifacts/openai/dummy_apk_sft.jsonl
```

Submit the fine-tuning job to OpenAI:

```bash
export OPENAI_API_KEY=...
python3 -B -m android_adk_rl_env.openai_finetune submit --training-file artifacts/openai/dummy_apk_sft.jsonl --model gpt-4o-mini --suffix dummy-apk-rl
```

You can also create a tiny no-ADB bootstrap dataset:

```bash
python3 -B -m android_adk_rl_env.openai_finetune prepare-scripted --output artifacts/openai/dummy_apk_sft_bootstrap.jsonl
```


## RL-Only Local Training

This path does not use OpenAI fine-tuning or supervised examples. It trains a local tabular softmax policy from rewards returned by the APK environment.

Train against the real APK through ADB:

```bash
python3 -B -m android_adk_rl_env.rl_train \
  --episodes 50 \
  --eval-episodes 5 \
  --max-steps 10 \
  --checkpoint artifacts/rl/dummy_apk_policy.json \
  --compact
```

Benchmark a saved RL checkpoint:

```bash
python3 -B -m android_adk_rl_env.rl_benchmark \
  --checkpoint artifacts/rl/dummy_apk_policy.json \
  --episodes 10 \
  --output artifacts/rl/dummy_apk_rl_benchmark.jsonl \
  --compact
```

For a faster smoke test with a smaller action space:

```bash
python3 -B -m android_adk_rl_env.rl_train --episodes 1 --eval-episodes 1 --max-steps 8 --no-distractors --compact
```

Real APK RL is slow because every step uses ADB and UIAutomator. One episode can take tens of seconds depending on the device/emulator.


## AndroidWorld Backend

This repo has an optional AndroidWorld backend on the `androidworld-integration` branch. It maps repo actions to AndroidWorld `JSONAction`s and keeps the same dummy APK SharedPreferences reward.

Check availability:

```bash
python3 -B -m android_adk_rl_env.android_world_runner --status
```

Run with AndroidWorld when installed:

```bash
python3 -B -m android_adk_rl_env.android_world_runner --backend android_world --policy scripted --episodes 1 --install-apk --compact
```

See [docs/android_world_integration.md](docs/android_world_integration.md).
