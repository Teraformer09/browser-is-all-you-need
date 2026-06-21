"""Benchmark-style rollout metrics."""

from __future__ import annotations

from typing import Any


def summarize_task_results(task_results: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(task_results)
    rewards = [float(result.get("reward", result.get("final_reward", 0.0)) or 0.0) for result in task_results]
    steps = [int(result.get("steps", 0) or 0) for result in task_results]
    reset_durations = [
        float((result.get("reset_metadata") or {}).get("duration_seconds", 0.0) or 0.0)
        for result in task_results
        if result.get("reset_metadata") is not None
    ]
    prompt_tokens = [int(result.get("total_prompt_tokens", 0) or 0) for result in task_results]
    completion_tokens = [int(result.get("total_completion_tokens", 0) or 0) for result in task_results]
    return {
        "exact_success_rate": _ratio(sum(1 for result in task_results if result.get("exact_success")), count),
        "mean_shaped_reward": _mean(rewards),
        "mean_episode_steps": _mean(steps),
        "mean_reset_duration_seconds": _mean(reset_durations),
        "invalid_action_rate": _ratio(sum(int(result.get("invalid_action_count", 0) or 0) for result in task_results), sum(steps)),
        "safety_block_rate": _ratio(sum(int(result.get("safety_block_count", 0) or 0) for result in task_results), sum(steps)),
        "adb_error_rate": _ratio(sum(int(result.get("adb_error_count", 0) or 0) for result in task_results), sum(steps)),
        "timeout_rate": _ratio(sum(1 for result in task_results if result.get("failure_category") == "timeout"), count),
        "stale_episode_rejection_count": sum(int(result.get("stale_episode_rejection_count", 0) or 0) for result in task_results),
        "total_prompt_tokens": sum(prompt_tokens),
        "total_completion_tokens": sum(completion_tokens),
        "estimated_openai_cost_usd": _cost_or_none(task_results),
    }


def benchmark_alignment_metadata() -> dict[str, Any]:
    return {
        "real_adb": True,
        "dockerized_emulator": True,
        "fake_backend_allowed": False,
        "task_lifecycle_hooks": True,
        "shaped_rewards": True,
        "train_eval_splits": True,
        "seeded_randomization_available": True,
        "replay_buffer_available": True,
    }


def _mean(values: list[int | float]) -> float:
    return sum(float(value) for value in values) / len(values) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _cost_or_none(task_results: list[dict[str, Any]]) -> float | None:
    costs = [result.get("estimated_openai_cost_usd") for result in task_results if result.get("estimated_openai_cost_usd") is not None]
    if not costs:
        return None
    return float(sum(float(cost) for cost in costs))
