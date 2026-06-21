# SWE-RL Style Architecture Mapping (Mobile Variant)

Branch: `feature/mobile-rl-improvement-plan`

I cloned the reference repo to:
- `/data/Balram/prime-intellect-android-adk-rl-environments/SWE_RL`

## What was observed in `wootzapp/wootzapp_swe_rl`

- Unified CLI entrypoint:
  - `SWE_RL/scripts/w8rl.sh` (bash, subcommands, project/runtime checks, diagnostics)
- Core package split:
  - `SWE_RL/w8_rl/` (training, datasets, rollout, runtime/backends)
- Configuration-first design:
  - `SWE_RL/configs/*`
- Orchestrated docker flow:
  - `SWE_RL/docker-compose.ray.yml`
  - `SWE_RL/docker/`, `SWE_RL/scripts/*`
- Task materialization + benchmark assets:
  - `SWE_RL/tasks/*`, `w8_storage/*`

## Implemented in this repo

The SWE-RL control pattern is now implemented in this branch via:

- `configs/mobile/orchestrator.env` (central, editable defaults)
- `scripts/mobile_rl.sh` (single orchestrator CLI)
- `scripts/run_proof_benchmark.sh` + real ADB preflight as benchmark runner
- Existing AndroidWorld and Prime execution scripts, now wired through orchestrator commands

Current `mobile_rl.sh` supports:

- `preflight` and `health`
- `benchmark proof|quick|release`
- `rollout`
- `prime-eval`
- `android-world`
- `pipeline`

Additional improvements now layered onto that SWE-RL-style control surface:

- `POOL_SIZE`-aware rollout and benchmark execution
- snapshot-first reset orchestration with full-reset fallback
- KVM-aware preflight checks
- standardized observation schema across ADB and AndroidWorld
- benchmark/rollout artifact summaries that include reset timing

`pipeline` follows a SWE-RL style staged flow:

1. preflight
2. benchmark (with screenshot collection)
3. rollout
4. optional Prime eval
5. optional AndroidWorld OpenAI

Defaults are controlled by `configs/mobile/orchestrator.env`.

## Current Validation State

- The orchestrator pattern is implemented and in active use.
- Real ADB preflight, benchmark, and rollout were re-run on `2026-06-21`.
- The live form-task path is working on the demo APK.
- The live ride-booking path still needs more task-specific debugging.

## Immediate concrete next steps

- Keep `mobile_rl.sh` as the canonical entrypoint for all mobile execution.
- Finish the ride-booking scripted-task fixes on the live emulator path.
- Revalidate Prime eval and AndroidWorld full runs after the runtime hardening changes.
