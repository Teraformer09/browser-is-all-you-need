"""Rollout collection for Android APK environments."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv


class Policy(Protocol):
    def reset(self) -> None: ...
    def act(self, observation: dict[str, Any]) -> ApkAction: ...


def run_rollouts(
    env_factory: Callable[[], DummyApkEnv],
    policy_factory: Callable[[], Policy],
    episodes: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for episode_index in range(episodes):
        env = env_factory()
        policy = policy_factory()
        if hasattr(policy, "reset"):
            policy.reset()
        observation = env.reset()
        transitions: list[dict[str, Any]] = []

        while not env.done:
            action = policy.act(observation)
            result = env.step(action)
            transitions.append(
                {
                    "observation": observation,
                    "action": action.to_dict(),
                    "next_observation": result.observation,
                    "reward": result.reward,
                    "done": result.done,
                    "info": result.info,
                }
            )
            observation = result.observation
            if result.done:
                break

        final_observation = observation
        results.append(
            {
                "episode": episode_index,
                "task": final_observation.get("task"),
                "goal": final_observation.get("goal"),
                "success": final_observation.get("final_reward", 0.0) >= 1.0,
                "reward": final_observation.get("reward", 0.0),
                "final_reward": final_observation.get("final_reward", 0.0),
                "steps": final_observation.get("steps", len(transitions)),
                "transitions": transitions,
                "final_observation": final_observation,
            }
        )
    return results


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
