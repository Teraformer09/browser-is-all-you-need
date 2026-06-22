"""Statistically strict pass@k helpers."""

from __future__ import annotations

import math
import random
from statistics import mean


def unbiased_pass_at_k(n: int, c: int, k: int) -> float:
    if n <= 0:
        raise ValueError("n must be positive")
    if c < 0 or c > n:
        raise ValueError(f"invalid success count c={c} for n={n}")
    if k <= 0:
        raise ValueError("k must be positive")
    if k > n:
        raise ValueError(f"requested k={k} exceeds available samples n={n}")
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - (math.comb(n - c, k) / math.comb(n, k))


def compute_pass_at_k(successes_by_task: dict[str, list[bool]], k_values: list[int]) -> dict[str, float]:
    if not successes_by_task:
        return {f"pass@{k}": 0.0 for k in k_values}

    sample_count = _uniform_sample_count(successes_by_task)
    return {
        f"pass@{k}": mean(
            unbiased_pass_at_k(sample_count, sum(1 for ok in successes if ok), k)
            for successes in successes_by_task.values()
        )
        for k in k_values
    }


def summarize_pass_at_k(
    successes_by_task: dict[str, list[bool]],
    k_values: list[int],
    *,
    bootstrap_samples: int = 0,
    bootstrap_seed: int = 17230,
) -> dict[str, dict[str, float | int]]:
    if not successes_by_task:
        return {
            f"pass@{k}": {"mean": 0.0, "p2_5": 0.0, "p97_5": 0.0, "samples": 0}
            for k in k_values
        }

    sample_count = _uniform_sample_count(successes_by_task)
    values_by_k: dict[str, list[float]] = {}
    for k in k_values:
        values_by_k[f"pass@{k}"] = [
            unbiased_pass_at_k(sample_count, sum(1 for ok in successes if ok), k)
            for successes in successes_by_task.values()
        ]
    rng = random.Random(bootstrap_seed)
    return {
        metric: bootstrap_mean_confidence_interval(values, samples=bootstrap_samples, rng=rng)
        for metric, values in values_by_k.items()
    }


def bootstrap_mean_confidence_interval(
    values: list[float],
    *,
    samples: int,
    rng: random.Random,
) -> dict[str, float | int]:
    if not values:
        return {"mean": 0.0, "p2_5": 0.0, "p97_5": 0.0, "samples": 0}
    if samples <= 0:
        avg = mean(values)
        return {"mean": avg, "p2_5": avg, "p97_5": avg, "samples": 0}

    size = len(values)
    resampled_means: list[float] = []
    for _ in range(samples):
        sample = [values[rng.randrange(size)] for _ in range(size)]
        resampled_means.append(mean(sample))
    resampled_means.sort()
    low_idx = int((len(resampled_means) - 1) * 0.025)
    high_idx = int((len(resampled_means) - 1) * 0.975)
    return {
        "mean": mean(values),
        "p2_5": float(resampled_means[low_idx]),
        "p97_5": float(resampled_means[high_idx]),
        "samples": samples,
    }


def _uniform_sample_count(successes_by_task: dict[str, list[bool]]) -> int:
    counts = {len(values) for values in successes_by_task.values()}
    if len(counts) != 1:
        raise ValueError(f"pass@k requires equal samples per task, got counts={sorted(counts)}")
    sample_count = counts.pop()
    if sample_count <= 0:
        raise ValueError("pass@k requires at least one sample per task")
    return sample_count
