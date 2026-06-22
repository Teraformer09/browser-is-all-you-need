# CLI, Benchmarking, and Reward Upgrade

Last updated: 2026-06-22

This document tracks the go-live upgrade that added the spec-driven CLI, strict benchmark math, and reward reporting surface.

## Implemented

- `mobile-rl` CLI entrypoint at `android_adk_rl_env/cli.py`
- YAML task specs in top-level `tasks/*.yaml`
- Registered verifier checks in `android_adk_rl_env/tasks/checks/`
- Shared spec execution layer in `android_adk_rl_env/eval_runner.py`
- Strict unbiased `pass@k` utilities in `android_adk_rl_env/benchmarking/pass_at_k.py`
- Reward distribution, best-of-k, and calibration helpers in `android_adk_rl_env/benchmarking/reward_stats.py`
- Spec-driven benchmark runner in `android_adk_rl_env/proof_benchmark.py`
- Makefile benchmark targets rewritten as thin wrappers over the new CLI

## Live-validated Today

- `python3 -m android_adk_rl_env.cli health`
- `python3 -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted`

Observed result:

- harness health check passed on serial `127.0.0.1:15555`
- scripted form task returned `harness_success=true`
- scripted form task returned `task_success=true`
- snapshot creation failure degraded cleanly to full reset instead of aborting the run

## Test Coverage Added

- `tests/unit/test_pass_at_k.py`
- `tests/unit/test_reward_calibration.py`
- `tests/unit/test_task_specs.py`

## Important Semantics

- `mobile-rl eval` exits `0` when the harness runs successfully, even if the task fails.
- `mobile-rl eval` exits non-zero only for harness/runtime failure.
- `pass@k` now raises if `k` exceeds the number of collected samples per task.
- Reward reports include per-task thresholds and aggregate best-of-k summaries.

## Remaining Validation Gap

- The benchmark CLI and ride-task specs are implemented, but they were not fully revalidated end to end on live hardware in this pass.
