"""Local RL-only trainer for the dummy APK environment.

This trains a small stochastic policy from environment rewards. It does not use
OpenAI fine-tuning, imitation learning, or demonstration labels.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.rollout import write_jsonl


@dataclass(frozen=True)
class RlTrainConfig:
    episodes: int = 50
    max_steps: int = 10
    learning_rate: float = 0.15
    gamma: float = 0.95
    entropy_coef: float = 0.01
    invalid_action_penalty: float = -0.05
    success_bonus: float = 1.0
    seed: int = 7


class CandidateActionSpace:
    """Finite Android action set used by the local RL trainer."""

    def __init__(self, task: DummyApkFormSearchTask | None = None, include_distractors: bool = True) -> None:
        task = task or DummyApkFormSearchTask()
        actions = [
            ApkAction("input_resource", target="search_input", text=task.query),
            ApkAction("click_resource", target="search_button"),
            ApkAction("input_resource", target="name_input", text=task.name),
            ApkAction("input_resource", target="email_input", text=task.email),
            ApkAction("press_back"),
            ApkAction("click_resource", target="submit_button"),
            ApkAction("wait"),
            ApkAction("finish"),
        ]
        if include_distractors:
            actions.extend(
                [
                    ApkAction("input_resource", target="search_input", text="wrong query"),
                    ApkAction("input_resource", target="name_input", text="Wrong Name"),
                    ApkAction("input_resource", target="email_input", text="wrong@example.com"),
                    ApkAction("click_resource", target="name_input"),
                    ApkAction("click_resource", target="email_input"),
                ]
            )
        self.actions = actions

    def __len__(self) -> int:
        return len(self.actions)

    def __getitem__(self, index: int) -> ApkAction:
        return self.actions[index]

    def to_jsonable(self) -> list[dict[str, str | None]]:
        return [action.to_dict() for action in self.actions]

    @classmethod
    def from_jsonable(cls, rows: list[dict[str, Any]]) -> "CandidateActionSpace":
        obj = cls(include_distractors=False)
        obj.actions = [ApkAction.from_dict(row) for row in rows]
        return obj


class TabularSoftmaxPolicy:
    """State-conditioned categorical policy trained with policy gradient."""

    def __init__(
        self,
        action_space: CandidateActionSpace,
        seed: int = 7,
        preferences: dict[str, list[float]] | None = None,
    ) -> None:
        self.action_space = action_space
        self.rng = random.Random(seed)
        self.preferences: defaultdict[str, list[float]] = defaultdict(self._zeros)
        if preferences:
            for key, values in preferences.items():
                self.preferences[key] = list(values)

    def act(self, observation: dict[str, Any], greedy: bool = False) -> tuple[int, ApkAction, list[float], str]:
        state = state_key(observation)
        probs = self.probs(state)
        if greedy:
            index = max(range(len(probs)), key=probs.__getitem__)
        else:
            index = self._sample(probs)
        return index, self.action_space[index], probs, state

    def probs(self, state: str) -> list[float]:
        prefs = self.preferences[state]
        max_pref = max(prefs)
        exps = [math.exp(value - max_pref) for value in prefs]
        total = sum(exps)
        return [value / total for value in exps]

    def update(self, state: str, action_index: int, advantage: float, learning_rate: float, entropy_coef: float) -> None:
        probs = self.probs(state)
        prefs = self.preferences[state]
        for index, prob in enumerate(probs):
            indicator = 1.0 if index == action_index else 0.0
            entropy_push = -prob * math.log(max(prob, 1e-8))
            prefs[index] += learning_rate * (advantage * (indicator - prob) + entropy_coef * entropy_push)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "tabular_softmax_policy",
            "actions": self.action_space.to_jsonable(),
            "preferences": dict(self.preferences),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], seed: int = 7) -> "TabularSoftmaxPolicy":
        action_space = CandidateActionSpace.from_jsonable(data["actions"])
        return cls(action_space=action_space, seed=seed, preferences=data.get("preferences", {}))

    def _zeros(self) -> list[float]:
        return [0.0 for _ in range(len(self.action_space))]

    def _sample(self, probs: list[float]) -> int:
        threshold = self.rng.random()
        cumulative = 0.0
        for index, prob in enumerate(probs):
            cumulative += prob
            if threshold <= cumulative:
                return index
        return len(probs) - 1


def state_key(observation: dict[str, Any]) -> str:
    components = observation.get("reward_components") or {}
    ui = observation.get("ui") or []
    ui_text = {node.get("id"): node.get("text", "") for node in ui if isinstance(node, dict)}
    focus = next((node.get("id") for node in ui if isinstance(node, dict) and node.get("focused")), None)
    expected = observation.get("expected_state") or {}
    query_text = ui_text.get("search_input", "")
    name_text = ui_text.get("name_input", "")
    email_text = ui_text.get("email_input", "")
    key = {
        "step": min(int(observation.get("steps", 0)), 8),
        "query_saved": bool(components.get("query")),
        "name_saved": bool(components.get("name")),
        "email_saved": bool(components.get("email")),
        "submitted": bool(components.get("submitted")),
        "query_typed": query_text == expected.get("query"),
        "name_typed": name_text == expected.get("name"),
        "email_typed": email_text == expected.get("email"),
        "focus": focus,
    }
    return json.dumps(key, sort_keys=True)


def train_policy(
    env_factory: Any,
    config: RlTrainConfig,
    action_space: CandidateActionSpace | None = None,
) -> tuple[TabularSoftmaxPolicy, list[dict[str, Any]]]:
    action_space = action_space or CandidateActionSpace()
    policy = TabularSoftmaxPolicy(action_space=action_space, seed=config.seed)
    random.seed(config.seed)
    episodes: list[dict[str, Any]] = []

    for episode_index in range(config.episodes):
        env = env_factory()
        observation = env.reset()
        previous_reward = float(observation.get("reward", 0.0))
        transitions: list[dict[str, Any]] = []

        while not env.done:
            action_index, action, probs, state = policy.act(observation)
            result = env.step(action)
            current_reward = float(result.reward)
            reward_delta = current_reward - previous_reward
            previous_reward = current_reward
            if result.info.get("invalid_action"):
                reward_delta += config.invalid_action_penalty
            if result.done and result.info.get("final_reward", 0.0) >= 1.0:
                reward_delta += config.success_bonus

            transitions.append(
                {
                    "state": state,
                    "action_index": action_index,
                    "action": action.to_dict(),
                    "reward_delta": reward_delta,
                    "reward": current_reward,
                    "final_reward": result.info.get("final_reward", 0.0),
                    "done": result.done,
                    "info": result.info,
                    "probs": probs,
                }
            )
            observation = result.observation
            if result.done:
                break

        returns = discounted_returns([float(t["reward_delta"]) for t in transitions], gamma=config.gamma)
        baseline = sum(returns) / len(returns) if returns else 0.0
        for transition, value in zip(transitions, returns):
            policy.update(
                state=transition["state"],
                action_index=int(transition["action_index"]),
                advantage=value - baseline,
                learning_rate=config.learning_rate,
                entropy_coef=config.entropy_coef,
            )

        episodes.append(
            {
                "episode": episode_index,
                "success": observation.get("final_reward", 0.0) >= 1.0,
                "reward": observation.get("reward", 0.0),
                "final_reward": observation.get("final_reward", 0.0),
                "steps": observation.get("steps", len(transitions)),
                "transitions": transitions,
            }
        )
    return policy, episodes


def evaluate_policy(env_factory: Any, policy: TabularSoftmaxPolicy, episodes: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for episode_index in range(episodes):
        env = env_factory()
        observation = env.reset()
        transitions: list[dict[str, Any]] = []
        while not env.done:
            action_index, action, probs, state = policy.act(observation, greedy=True)
            result = env.step(action)
            transitions.append(
                {
                    "state": state,
                    "action_index": action_index,
                    "action": action.to_dict(),
                    "reward": result.reward,
                    "done": result.done,
                    "info": result.info,
                    "probs": probs,
                }
            )
            observation = result.observation
            if result.done:
                break
        results.append(
            {
                "episode": episode_index,
                "success": observation.get("final_reward", 0.0) >= 1.0,
                "reward": observation.get("reward", 0.0),
                "final_reward": observation.get("final_reward", 0.0),
                "steps": observation.get("steps", len(transitions)),
                "transitions": transitions,
            }
        )
    return results


def discounted_returns(rewards: list[float], gamma: float) -> list[float]:
    values: list[float] = []
    running = 0.0
    for reward in reversed(rewards):
        running = reward + gamma * running
        values.append(running)
    return list(reversed(values))


def save_checkpoint(path: str | Path, policy: TabularSoftmaxPolicy, config: RlTrainConfig) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"config": config.__dict__, "policy": policy.to_dict()}
    target.write_text(json.dumps(payload, indent=2, sort_keys=True))


def load_checkpoint(path: str | Path, seed: int = 7) -> TabularSoftmaxPolicy:
    data = json.loads(Path(path).read_text())
    return TabularSoftmaxPolicy.from_dict(data["policy"], seed=seed)


def summarize_episodes(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(episodes)
    successes = sum(1 for episode in episodes if episode.get("success"))
    return {
        "episodes": count,
        "successes": successes,
        "success_rate": successes / count if count else 0.0,
        "average_reward": sum(float(ep.get("reward", 0.0)) for ep in episodes) / count if count else 0.0,
        "average_final_reward": sum(float(ep.get("final_reward", 0.0)) for ep in episodes) / count if count else 0.0,
        "average_steps": sum(int(ep.get("steps", 0)) for ep in episodes) / count if count else 0.0,
    }


def save_episodes(path: str | Path, episodes: list[dict[str, Any]]) -> None:
    write_jsonl(path, episodes)


def make_env_factory(task: DummyApkFormSearchTask, max_steps: int, shaped_rewards: bool = True) -> Any:
    def factory() -> DummyApkEnv:
        return DummyApkEnv(task=task, max_steps=max_steps, shaped_rewards=shaped_rewards)

    return factory
