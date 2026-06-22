# Throughput Benchmark

Last updated: 2026-06-22

This document is the publication-facing place to record throughput, reset latency, and scaling efficiency.

## Goal

Measure real performance rather than asserting it.

Target metrics:

- rollouts/sec
- env-steps/sec
- reset latency by mode
- scaling efficiency

## Benchmark Driver

CLI:

```bash
python3 -m android_adk_rl_env.benchmarking.throughput \
  --pool-sizes 1 2 4 8 \
  --attempts-per-instance 10 \
  --pass-k 1 2 3 5 10 \
  --output artifacts/throughput
```

Generated artifact:

```text
artifacts/throughput/throughput_summary.json
```

## Scaling Efficiency Definition

```text
scaling_efficiency(pool_size=N)
= rollouts_per_second_at_N / (N * rollouts_per_second_at_1)
```

## Result Table

Measured on 2026-06-22 using the scripted benchmark policy and the four current task specs.

| Pool size | Rollouts/sec | Env-steps/sec | Avg reset s | Scaling efficiency | Notes |
|---|---:|---:|---:|---:|---|
| 1 | 0.0294 | 0.1395 | 9.2095 | 1.0000 | `artifacts/throughput/publication/pool_1/20260622_053823` |
| 2 | 0.0604 | 0.2870 | 9.1848 | 1.0285 | `artifacts/throughput/publication/pool_2/20260622_054039` |
| 4 | not measured | not measured | not measured | not measured | additional provisioned devices required |
| 8 | not measured | not measured | not measured | not measured | additional provisioned devices required |

## Measurement Notes

- benchmark artifact:
  - `artifacts/throughput/publication/throughput_summary.json`
- task count:
  - `4`
- attempts per task instance:
  - `1`
- reset mode during the measured runs:
  - `full`
- observed reset latency by mode:
  - all measured runs used `full` reset

## Interpretation

- Pool size `2` delivered slightly better than linear scaling relative to pool size `1` on this host.
- The measured speedup is credible for the current scripted benchmark because the two emulators were active concurrently and the underlying benchmark rows record overlapping timestamps.
- These results should be treated as host-specific until reproduced on additional hardware and at larger pool sizes.

## Current Status

- Throughput benchmark code is implemented in `android_adk_rl_env/benchmarking/throughput.py`.
- Real measured results now exist for pool sizes `1` and `2`.
- Publication-grade scaling claims beyond `2` devices still need more provisioned hardware.
