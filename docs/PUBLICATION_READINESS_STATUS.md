# Publication Readiness Status

Last updated: 2026-06-22

This document tracks the publication-readiness checklist from the "Path to Publication" review and records only completed or directly observed facts.

## Pillar 0 Prerequisites

### 0.1 Device pool validated with `POOL_SIZE >= 2`

Status: `completed`

Evidence:

- live pool validation run:
  - artifact dir: `artifacts/benchmarks/pool2-validate/20260622_052518`
- distinct serials observed:
  - `127.0.0.1:15555`
  - `emulator-5556`
- overlapping timestamps observed:
  - `form_default` started `2026-06-22T05:25:18.349097+00:00`
  - `form_randomized` started `2026-06-22T05:25:18.350177+00:00`

### 0.2 Snapshot reset failure mode captured

Status: `completed`

Root cause:

- the main live emulator path is exposed as ADB-over-TCP serial `127.0.0.1:15555`
- this path is an emulator, but not a console-style `emulator-####` serial
- `adb emu avd snapshot ...` therefore is not a reliable control path for that serial

Observed split:

- on `emulator-5556`, raw snapshot commands succeeded:
  - `adb -s emulator-5556 emu avd snapshot list`
  - `adb -s emulator-5556 emu avd snapshot save codex_diag_snapshot`
  - `adb -s emulator-5556 emu avd snapshot load codex_diag_snapshot`
- on `127.0.0.1:15555`, raw snapshot commands failed:
  - `adb -s 127.0.0.1:15555 emu avd snapshot list`
  - `adb -s 127.0.0.1:15555 emu avd snapshot save codex_tcp_snapshot`
  - `adb -s 127.0.0.1:15555 emu avd snapshot load codex_tcp_snapshot`
  - observed shell exit code: `1`

Fix applied:

- snapshot support now checks for emulator-console capability
- TCP-attached emulator serials degrade directly to full reset instead of repeatedly attempting unsupported console snapshot commands

Observed post-fix behavior:

- with `RESET_MODE=snapshot`, live eval on `127.0.0.1:15555` reports:
  - `applied_mode=full`
  - `baseline_snapshot=null`
  - `fallback_used=false`

### 0.3 Live benchmark with `samples-per-task >= 10`

Status: `completed`

Observed run:

- command:

```bash
RESET_MODE=full ADB_SERIALS='127.0.0.1:15555 emulator-5556' \
python3 -m android_adk_rl_env.proof_benchmark \
  --tasks-dir tasks \
  --attempts-per-instance 10 \
  --pass-k 1 2 3 5 10 \
  --pool-size 2 \
  --output artifacts/benchmarks/publication-live-pool2 \
  --compact
```

Observed result:

- artifact dir:
  - `artifacts/benchmarks/publication-live-pool2/20260622_052711`
- samples per task:
  - `10`
- total attempts:
  - `40`
- exact success rate:
  - `1.0`
- pass@k:
  - `pass@1=1.0`
  - `pass@2=1.0`
  - `pass@3=1.0`
  - `pass@5=1.0`
  - `pass@10=1.0`
- reward report:
  - aggregate sample count `10`
  - per-task reward mean `1.0`
  - per-task reward stddev `0.0`

### 0.4 One live Prime `vf-eval` run

Status: `completed`

Observed run:

```bash
env ADB_SERIAL=127.0.0.1:15555 START_EMULATOR=0 STOP_EMULATOR_AFTER_RUN=0 \
RESULTS_DIR=artifacts/prime_eval_android_adk/live_20260622 \
./scripts/run_prime_eval_android_adk.sh
```

Observed result:

- artifact:
  - `artifacts/prime_eval_android_adk/live_20260622/prime_eval.log`
- harness status:
  - completed
- task result:
  - reward `0.0`
  - turns `6`

Interpretation:

- Prime live eval is now validated as runnable on the real environment
- the current model-backed policy did not solve the task in the observed run, so this closes the runtime-validation gap but not the model-quality gap

### 0.5 One live AndroidWorld run

Status: `completed`

Observed run:

- command:

```bash
timeout 180 ./.venv/bin/python -u -B -m android_adk_rl_env.android_world_runner \
  --backend android_world \
  --policy scripted \
  --episodes 1 \
  --max-steps 10 \
  --output artifacts/android_world/scripted_smoke.jsonl \
  --adb-path adb \
  --adb-serial emulator-5556 \
  --console-port 5556 \
  --grpc-port 8555 \
  --compact
```

Observed result:

- summary:

```json
{"android_world_installed": true, "backend": "android_world", "episodes": 1, "output": "artifacts/android_world/scripted_smoke.jsonl", "policy": "scripted", "success_rate": 1.0, "successes": 1}
```

- rollout artifact:
  - `artifacts/android_world/scripted_smoke.jsonl`
- runtime requirement captured:
  - the emulator must be launched with an explicit gRPC port such as `-grpc 8555`

## Pillar A Speed Work

### A1 Throughput benchmarking suite

Status: `implemented and measured on supported local hardware`

Added:

- `android_adk_rl_env/benchmarking/throughput.py`
- `docs/THROUGHPUT_BENCHMARK.md`
- `make throughput-benchmark`
- `make mobile-throughput`

Remaining:

- local host currently has measured runs for pool sizes `1` and `2`
- pool sizes `4` and `8` still require additional provisioned devices before publication can claim those points

### A2 Hybrid fast-path backend for training

Status: `not started`

### A3 Portability path

Status: `partially implemented`

Implemented:

- KVM-aware setup and emulator-oriented architecture

Still needed:

- explicit cross-host validation with measured output

## Pillar B Novel Benchmark Contribution

### B1 Cross-app app-pair families

Status: `not started`

Current benchmark scope:

- form completion
- ride booking
- ride cancel

These are single-app tasks, not yet the cross-app benchmark required for a novel benchmark paper.

### B2 Verifier methodology writeup

Status: `partially implemented`

Relevant docs:

- `docs/REWARDS.md`
- `docs/FULL_ARCHITECTURE_IMPLEMENTATION.md`
- `docs/BENCHMARK_AND_ENVIRONMENT_CARD.md`

Still needed:

- explicit cross-app verifier methodology once cross-app tasks exist

### B3 Release shape under `environments/<name>/`

Status: `partially implemented`

Current supporting structure exists in:

- `prime_android_adk_rl_env/`
- `environments/mobile_android_rl/`

Still needed:

- cross-app benchmark content published in the same convention

## Pillar C Evaluation Rigor

### C1 Baseline policies

Status: `partially implemented`

Implemented in code:

- scripted policy
- random policy
- OpenAI policy path

Still needed:

- real benchmark table with random / oracle / zero-shot model numbers
- broader live comparison beyond the currently measured oracle and broken-policy paths

### C2 Comparative system table

Status: `started`

Added:

- `docs/COMPETITIVE_POSITIONING.md`

Still needed:

- replace the conservative placeholders with sourced or newly measured comparison numbers

### C3 Cross-app calibration

Status: `partially implemented`

Implemented:

- live oracle benchmark path:
  - `artifacts/benchmarks/publication-live-pool2/20260622_052711`
- live broken-policy benchmark path:
  - `artifacts/benchmarks/broken-live-form/20260622_095050`
  - `artifacts/benchmarks/broken-live-ride/20260622_115043`

Observed live broken-policy result for form tasks:

- policy:
  - `broken`
- task scope:
  - `form_default`
  - `form_randomized`
- total attempts:
  - `6`
- exact success rate:
  - `0.0`
- pass@1:
  - `0.0`
- pass@2:
  - `0.0`
- pass@3:
  - `0.0`
- shaped reward mean:
  - `0.15`

Observed live broken-policy result for ride tasks:

- policy:
  - `broken`
- task scope:
  - `ride_cheapest_001`
  - `ride_cancel_001`
- total attempts:
  - `6`
- exact success rate:
  - `0.0`
- pass@1:
  - `0.0`
- pass@2:
  - `0.0`
- pass@3:
  - `0.0`
- shaped reward mean:
  - `0.18`

Reward-design note:

- an earlier live ride calibration run produced shaped reward mean `0.5` for the broken policy
- ride shaped reward was then tightened to reduce credit for trivial progress
- the corrected live rerun dropped broken-policy ride reward to `0.18`

Still needed:

- cross-app calibration once cross-app tasks exist
- a live random or zero-shot model comparison table across the broader benchmark family

## Pillar D Trainability

### D1 Real training loop

Status: `not started`

### D2 Trained vs untrained comparison

Status: `not started`

## Pillar E Competitive Positioning

Status: `started`

Added:

- `docs/COMPETITIVE_POSITIONING.md`

## Pillar F Publication Packaging

### F1 Environment / benchmark card

Status: `completed`

Added:

- `docs/BENCHMARK_AND_ENVIRONMENT_CARD.md`

### F2 Reproducibility

Status: `partially implemented`

Implemented:

- vendored `third_party/android_world` copy at commit `d9c569f764b3a5629321858de03ff653d0f24056`
- task specs and benchmark config artifacts
- reset-mode and device-serial reporting

Still needed:

- final paper-grade reproducibility section with exact reported-run commit/image pinning

### F3 Release plan

Status: `completed`

Added:

- `docs/PUBLICATION_RELEASE_PLAN.md`
- `docs/COMPETITIVE_POSITIONING.md`
