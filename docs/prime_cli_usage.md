# Prime Intellect CLI Usage

This repo now exposes an official Prime/verifiers environment entry point:

```python
from prime_android_adk_rl_env import load_environment
```

`load_environment(**kwargs)` returns a `verifiers.MultiTurnEnv` backed by the real dummy Android APK.

## Local Smoke Load

```bash
PYTHONPATH=. prime eval run prime_android_adk_rl_env \
  --provider openai \
  --model gpt-4o-mini \
  --api-key-var OPENAI_API_KEY \
  --num-examples 1 \
  --rollouts-per-example 1 \
  --max-concurrent 1 \
  --env-args '{"backend":"adb","max_turns":15}' \
  --skip-upload \
  --disable-env-server
```

For convenience, this repo provides:

```bash
./scripts/run_prime_eval_android_adk.sh
```

The script loads `.env`, builds and installs the dummy APK, then runs `prime eval run` against the official `prime_android_adk_rl_env` module.

## Environment Args

| Arg | Default | Description |
|---|---:|---|
| `backend` | `adb` | `adb` or `android_world`. |
| `adb_path` | `adb` | ADB executable path. |
| `adb_serial` | `null` | Optional ADB serial, such as `emulator-5556`. |
| `console_port` | `5556` | AndroidWorld emulator console port. |
| `grpc_port` | `8554` | AndroidWorld gRPC port. |
| `max_turns` | `15` | Max model/environment turns. |
| `max_examples` | `1` | Dataset size exposed to Prime eval. |

## Push To Prime Environment Hub

When authenticated with Prime CLI:

```bash
prime login
prime env push --path . --name prime-android-adk-rl-env --visibility PRIVATE
```

The package metadata is in `pyproject.toml`, and the verifiers entry point is `prime_android_adk_rl_env.load_environment`.

## Relationship To AndroidWorld Script

`./scripts/run_android_world_openai.sh` remains the full AndroidWorld + video/screenshot artifact runner.

`./scripts/run_prime_eval_android_adk.sh` is the Prime CLI/verifiers runner. It uses the same dummy APK reward contract and can use either ADB or AndroidWorld as the backend via `PRIME_ANDROID_BACKEND`.
