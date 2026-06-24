# Benchmark and Environment Card

Last updated: 2026-06-23

## Scope

This repo exposes a mobile-agent benchmark and RL environment around the demo APK `com.primeintellect.dummyrl`.

## Supported Task Families

- single-app form completion
- single-app ride booking
- single-app ride cancel
- Uber clone ride booking benchmark

Current task specs:

- `tasks/form_default.yaml`
- `tasks/form_randomized.yaml`
- `tasks/ride_cheapest.yaml`
- `tasks/ride_cancel.yaml`
- `tasks/uber_clone/*.yaml` (`uber_clone_001.yaml` through `uber_clone_030.yaml`)

## Execution Modes

- real ADB-backed execution
- AndroidWorld integration surface
- AndroidWorld scripted live execution through a gRPC-enabled emulator
- benchmark repetition through `proof_benchmark.py`
- spec-driven eval through `mobile-rl`
- OpenAI-backed structured action policy for ride and form tasks

## Reward Methodology

- reward is read from durable app state
- shaped reward is fractional
- final reward is exact sparse success
- task success is determined by a registered verifier function plus threshold

## Uber Clone Notes

The Uber clone benchmark uses the same dummy APK package, but launches the ride surface directly and evaluates 30 YAML task specs.

The current ride flow exposes stable ids for:

- pickup entry
- ride-type selection
- destination search
- cab-type selection
- payment selection
- booking confirmation

A scripted eval of `tasks/uber_clone/uber_clone_001.yaml` succeeded on 2026-06-23.

## Current Limitations

- cross-app tasks are not implemented yet
- `OPENAI_API_KEY` is required for the OpenAI-backed benchmark and is not set in the current environment
- multi-device validation is still host-dependent
- throughput beyond pool size `2` still needs more provisioned devices

## Measured Validation Snapshot

Observed on 2026-06-23:

- single scripted Uber clone eval:
  - `tasks/uber_clone/uber_clone_001.yaml`
  - `exact_success=true`
  - `final_reward=1.0`
  - artifact: [ride_clone_screen.png](/tmp/ride_clone_screen_updated.png)
- pool validation:
  - `POOL_SIZE=2` validated with serials `127.0.0.1:15555` and `emulator-5556`
- release-style benchmark:
  - `40` total attempts
  - `samples-per-task=10`
  - `pass@1/2/3/5/10 = 1.0`
- throughput:
  - pool `1`: `0.0294` rollouts/sec
  - pool `2`: `0.0604` rollouts/sec
- AndroidWorld scripted run:
  - `success_rate=1.0`
  - artifact: `artifacts/android_world/scripted_smoke.jsonl`

## Reproducibility Inputs To Pin

- repo commit
- Android SDK version
- AVD image / system image
- emulator ports and serials
- `RESET_MODE`
- `ADB_CMD_TIMEOUT_S`
- vendored `third_party/android_world` copy at commit `d9c569f764b3a5629321858de03ff653d0f24056`
- `POLICY`
- model/provider/api settings when model-based runs are used
- explicit emulator gRPC port for AndroidWorld runs
