"""Episode-safe reward helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RewardResult:
    reward: float
    exact_success: bool
    components: dict[str, bool]
    shaped_components: dict[str, float]


def exact_success(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return bool(expected) and bool(actual) and all(_normalize(actual.get(key)) == _normalize(value) for key, value in expected.items())


def reward_components(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, bool]:
    return {key: _normalize(actual.get(key)) == _normalize(value) for key, value in expected.items()}


def shaped_reward(components: dict[str, bool]) -> float:
    if not components:
        return 0.0
    return sum(1 for passed in components.values() if passed) / len(components)


def evaluate_reward(expected: dict[str, Any], actual: dict[str, Any]) -> RewardResult:
    components = reward_components(expected, actual)
    success = bool(components) and all(components.values())
    shaped = {key: 1.0 if value else 0.0 for key, value in components.items()}
    return RewardResult(
        reward=shaped_reward(components),
        exact_success=success,
        components=components,
        shaped_components=shaped,
    )


def _normalize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)
