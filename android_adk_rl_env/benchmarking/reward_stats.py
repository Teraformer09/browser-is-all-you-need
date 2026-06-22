"""Reward reporting and calibration helpers."""

from __future__ import annotations

import itertools
import math
import random
from statistics import mean
from typing import Any

from android_adk_rl_env.benchmarking.pass_at_k import bootstrap_mean_confidence_interval


def summarize_reward_distributions(
    rewards_by_task: dict[str, list[float]],
    *,
    thresholds: dict[str, float],
    k_values: list[int],
    bootstrap_samples: int = 0,
    bootstrap_seed: int = 17230,
) -> dict[str, Any]:
    if not rewards_by_task:
        return {"per_task": {}, "aggregate": {"best_of_k": {}, "task_success_rate": 0.0}}

    sample_count = _uniform_sample_count(rewards_by_task)
    rng = random.Random(bootstrap_seed)
    per_task = {
        task_id: _task_reward_summary(rewards, threshold=thresholds[task_id], k_values=k_values)
        for task_id, rewards in rewards_by_task.items()
    }

    best_of_k: dict[str, dict[str, float | int]] = {}
    for k in k_values:
        if k > sample_count:
            raise ValueError(f"requested k={k} exceeds available samples n={sample_count}")
        values = [_expected_best_of_k(rewards, k) for rewards in rewards_by_task.values()]
        best_of_k[f"best_of_{k}"] = bootstrap_mean_confidence_interval(values, samples=bootstrap_samples, rng=rng)

    task_success_values = [
        1.0 if max(rewards) >= thresholds[task_id] else 0.0
        for task_id, rewards in rewards_by_task.items()
    ]
    return {
        "per_task": per_task,
        "aggregate": {
            "sample_count": sample_count,
            "task_success_rate": mean(task_success_values),
            "task_success_rate_ci": bootstrap_mean_confidence_interval(task_success_values, samples=bootstrap_samples, rng=rng),
            "best_of_k": best_of_k,
        },
    }


def check_reward_calibration(
    *,
    good_policy_rewards: dict[str, list[float]],
    bad_policy_rewards: dict[str, list[float]],
    thresholds: dict[str, float],
    target_good_floor: float = 0.95,
    target_bad_ceiling: float = 0.25,
    bootstrap_samples: int = 1000,
    bootstrap_seed: int = 17230,
) -> dict[str, Any]:
    good = summarize_reward_distributions(
        good_policy_rewards,
        thresholds=thresholds,
        k_values=[1],
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    bad = summarize_reward_distributions(
        bad_policy_rewards,
        thresholds=thresholds,
        k_values=[1],
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed + 1,
    )
    good_ci = good["aggregate"]["task_success_rate_ci"]
    bad_ci = bad["aggregate"]["task_success_rate_ci"]
    return {
        "good_policy": good,
        "bad_policy": bad,
        "targets": {
            "good_floor": target_good_floor,
            "bad_ceiling": target_bad_ceiling,
        },
        "passes": bool(good_ci["p2_5"] >= target_good_floor and bad_ci["p97_5"] <= target_bad_ceiling),
    }


def _task_reward_summary(rewards: list[float], *, threshold: float, k_values: list[int]) -> dict[str, Any]:
    ordered = [float(value) for value in rewards]
    success_count = sum(1 for value in ordered if value >= threshold)
    return {
        "threshold": threshold,
        "count": len(ordered),
        "min": min(ordered),
        "max": max(ordered),
        "mean": mean(ordered),
        "stddev": _stddev(ordered),
        "success_rate": float(success_count) / float(len(ordered)),
        "best_of_k": {
            f"best_of_{k}": _expected_best_of_k(ordered, k)
            for k in k_values
        },
    }


def _expected_best_of_k(rewards: list[float], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    if k > len(rewards):
        raise ValueError(f"requested k={k} exceeds available samples n={len(rewards)}")
    maxima = [max(combo) for combo in itertools.combinations(rewards, k)]
    return mean(maxima)


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / float(len(values))
    return math.sqrt(variance)


def _uniform_sample_count(values_by_task: dict[str, list[float]]) -> int:
    counts = {len(values) for values in values_by_task.values()}
    if len(counts) != 1:
        raise ValueError(f"reward reporting requires equal samples per task, got counts={sorted(counts)}")
    count = counts.pop()
    if count <= 0:
        raise ValueError("reward reporting requires at least one sample per task")
    return count
