"""Rollout row helpers."""

from __future__ import annotations

from typing import Any


def rollout_row(
    episode_id: str,
    task_id: str,
    step: int,
    observation: dict[str, Any],
    action: dict[str, Any],
    reward: float,
    done: bool,
    info: dict[str, Any],
) -> dict[str, Any]:
    return {
        "episode_id": episode_id,
        "task_id": task_id,
        "step": step,
        "observation": observation,
        "action": action,
        "reward": reward,
        "done": done,
        "info": info,
    }
