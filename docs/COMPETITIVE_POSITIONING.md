# Competitive Positioning

Last updated: 2026-06-22

This table is intentionally conservative. It records this repo's measured status and leaves unresolved comparisons blank instead of guessing.

| System | #apps | #tasks | Real/Sim | Cross-app | Parallel throughput | RL-trainable | Reward | Trainer integration |
|---|---:|---:|---|---|---|---|---|---|
| AndroidWorld | public benchmark | public benchmark | Real | No | not filled here | not filled here | Fractional | not filled here |
| AndroidLab | public benchmark | public benchmark | Real | No | not filled here | not filled here | not filled here | not filled here |
| DigiRL | not filled here | not filled here | Real | No | not filled here | Yes | not filled here | custom |
| MobileGym | not filled here | not filled here | Sim | No | not filled here | not filled here | not filled here | not filled here |
| This repo, current measured state | 1 demo app | 4 task specs | Real + AndroidWorld bridge | No | 0.0294 rollouts/sec at pool 1, 0.0604 at pool 2 | training code exists, no publication-grade curve yet | Fractional + exact success | Prime / `verifiers` native |

## What Can Be Claimed Today

- real ADB execution is validated
- AndroidWorld scripted execution is validated
- pool size `2` concurrency is validated
- throughput numbers for pool sizes `1` and `2` are measured
- Prime-compatible environment structure exists

## What Should Not Be Claimed Yet

- cross-app benchmark leadership
- model quality leadership
- training effectiveness
- throughput beyond the measured host and pool sizes
- successful Prime live eval without the missing API key
