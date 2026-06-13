"""Rollout collection for Android APK environments."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.training.failure_analysis import analyze_rollout


class Policy(Protocol):
    def reset(self) -> None: ...
    def act(self, observation: dict[str, Any]) -> ApkAction: ...
    def get_last_metadata(self) -> dict[str, Any]: ...


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
            metadata = policy.get_last_metadata() if hasattr(policy, "get_last_metadata") else {}
            transitions.append(
                {
                    "observation": observation,
                    "action": action.to_dict(),
                    "next_observation": result.observation,
                    "reward": result.reward,
                    "done": result.done,
                    "info": result.info,
                    "policy_metadata": metadata,
                }
            )
            observation = result.observation
            if result.done:
                break

        final_observation = observation
        rollout = {
            "episode": episode_index,
            "task": final_observation.get("task"),
            "goal": final_observation.get("goal"),
            "success": final_observation.get("final_reward", 0.0) >= 1.0,
            "reward": final_observation.get("reward", 0.0),
            "final_reward": final_observation.get("final_reward", 0.0),
            "steps": final_observation.get("steps", len(transitions)),
            "transitions": transitions,
            "final_observation": final_observation,
            "total_prompt_tokens": sum(
                int(item.get("policy_metadata", {}).get("prompt_tokens", 0) or 0) for item in transitions
            ),
            "total_completion_tokens": sum(
                int(item.get("policy_metadata", {}).get("completion_tokens", 0) or 0) for item in transitions
            ),
            "estimated_openai_cost_usd": None,
        }
        rollout.update(analyze_rollout(rollout))
        results.append(rollout)
    return results


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
