# Publication Release Plan

Last updated: 2026-06-22

This document turns the publication-readiness review into a concrete release checklist.

## What Is Already Closed

- `POOL_SIZE=2` validation with overlapping timestamps and two distinct serials
- snapshot reset root cause captured and hardened
- live benchmark run with `samples-per-task=10`
- live AndroidWorld scripted run on a gRPC-enabled emulator
- throughput measurement at pool sizes `1` and `2`
- environment card and architecture docs

## What Still Blocks A Publishable Claim

### External-run blockers

- one live Prime `vf-eval` run with saved output
- any OpenAI-backed run that requires `OPENAI_API_KEY`

### Scope blockers

- cross-app benchmark families are not implemented yet
- baseline comparison table is not populated with random, oracle, and zero-shot model results
- trainability evidence is not present yet
- held-out before/after training comparison is not present yet

## Release Sequence

1. Run live Prime eval once `OPENAI_API_KEY` is available.
2. Add at least one benchmark results table covering random, scripted, and zero-shot model baselines.
3. Implement the first cross-app task family and its verifier spec.
4. Run one real training loop and save the learning curve artifacts.
5. Fill the competitive positioning table with measured numbers only.
6. Freeze the exact commit, AVD image, and dependency refs used for the reported results.

## Minimum Artifact Bundle

- benchmark summary JSON
- reward report JSON
- throughput summary JSON
- AndroidWorld rollout JSONL
- Prime eval log
- repo commit hash
- system-image / AVD identifier
- config snapshot from `configs/mobile/orchestrator.env`

## Recommended Command Set

```bash
python3 -m android_adk_rl_env.cli benchmark --tasks-dir tasks --samples-per-task 10 --pass-k 1 2 3 5 10 --pool-size 2 --compact
python3 -m android_adk_rl_env.benchmarking.throughput --pool-sizes 1 2 --attempts-per-instance 1 --pass-k 1 --output artifacts/throughput/publication --compact
./.venv/bin/python -B -m android_adk_rl_env.android_world_runner --backend android_world --policy scripted --episodes 1 --max-steps 10 --output artifacts/android_world/scripted_smoke.jsonl --adb-serial emulator-5556 --console-port 5556 --grpc-port 8555 --compact
./scripts/run_prime_eval_android_adk.sh
```
