# Benchmark and Environment Card

Last updated: 2026-06-22

## Scope

This repo currently exposes a mobile-agent benchmark and RL environment around the demo APK `com.primeintellect.dummyrl`.

## Supported Task Families

- single-app form completion
- single-app ride booking
- single-app ride cancel

Current task specs:

- `tasks/form_default.yaml`
- `tasks/form_randomized.yaml`
- `tasks/ride_cheapest.yaml`
- `tasks/ride_cancel.yaml`

## Execution Modes

- real ADB-backed execution
- AndroidWorld integration surface
- AndroidWorld scripted live execution through a gRPC-enabled emulator
- benchmark repetition through `proof_benchmark.py`
- spec-driven eval through `mobile-rl`

## Reward Methodology

- reward is read from durable app state
- shaped reward is fractional
- final reward is exact sparse success
- task success is determined by a registered verifier function plus threshold

## Current Limitations

- cross-app tasks are not implemented yet
- the current benchmark family is deterministic under the scripted policy, so the current `samples-per-task=10` publication smoke run has zero reward variance
- Prime live eval still depends on `OPENAI_API_KEY`
- multi-device validation is still host-dependent
- throughput beyond pool size `2` still needs more provisioned devices

## Measured Validation Snapshot

Observed on 2026-06-22:

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
- `ANDROID_WORLD_REF`
- `POLICY`
- model/provider/api settings when model-based runs are used
- explicit emulator gRPC port for AndroidWorld runs
