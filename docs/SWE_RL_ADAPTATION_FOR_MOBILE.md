# SWE-RL Style Architecture Mapping (Mobile Variant)

Branch: `swe-rl-architecture`

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

## Recommended mobile adaptation plan (incremental)

1. Keep current Android environment package as the equivalent of `w8_rl`:
   - `android_adk_rl_env/` (already exists)
2. Introduce a light orchestration CLI, mirroring the SWE-RL style:
   - new `scripts/mobile_rl.sh` with subcommands:
     - `benchmark proof|quick|release`
     - `rollout`
     - `health`
     - `preflight`
3. Create a thin config layer for runs:
   - move hardcoded benchmark settings into `configs/mobile/*.json` or `.yaml`
4. Add a dedicated `runs/` artifact layout:
   - keep real outputs under `artifacts/mobile_runs/<run_id>/`
   - standard files: `summary.json`, `task_results.jsonl`, `rollout.jsonl`, `reward_trace.jsonl`, `replay.html`
5. Keep emulator lifecycle minimal initially:
   - rely on local `adb` + existing scripts for app install/healthcheck
   - avoid replacing existing working `run` path during first iteration
6. Build training/eval hooks only after benchmark and rollout are stable:
   - future: policy adapters for RL training entry points

## Immediate concrete next steps

- Verify branch has reference only for analysis and no accidental file collisions:
  - `git status`
- Add baseline mobile orchestrator script:
  - `scripts/mobile_rl.sh`
- Convert one existing path to config-driven execution:
  - `proof` benchmark flow
- Add simple docs:
  - `docs/mobilesdk_swe_rl_roadmap.md`.

## Important guardrails

- Keep the current real-ADB enforced benchmark wrapper as-is (already now includes device checks).
- Do not commit the cloned reference repo unless explicitly requested; keep it as local analysis reference.

