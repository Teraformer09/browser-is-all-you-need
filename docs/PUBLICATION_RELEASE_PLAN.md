# Publication Release Plan

Last updated: 2026-06-22

This document turns the publication-readiness review into a concrete release checklist.

For the tightly scoped next-round priorities, see:

- `docs/NEXT_HANDOFF_PRIORITY_SCOPE.md`

## What Is Already Closed

- `POOL_SIZE=2` validation with overlapping timestamps and two distinct serials
- snapshot reset root cause captured and hardened
- live benchmark run with `samples-per-task=10`
- live AndroidWorld scripted run on a gRPC-enabled emulator
- throughput measurement at pool sizes `1` and `2`
- environment card and architecture docs

## What Still Blocks A Publishable Claim

### External-run blockers

- improved Prime live-eval task success beyond the currently validated runnable harness path
- AndroidWorld OpenAI-path validation

### Scope blockers

- cross-app benchmark families are not implemented yet
- baseline comparison table is not populated with random, oracle, and zero-shot model results
- trainability evidence is not present yet
- held-out before/after training comparison is not present yet

## Release Sequence

1. Resolve the `127.0.0.1:15555` snapshot-topology question explicitly.
2. Improve or precisely diagnose the current Prime live-eval failure mode.
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
