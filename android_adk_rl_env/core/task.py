"""JSONL task loading utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_FORM_REWARD_WEIGHTS: dict[str, float] = {
    "episode_match": 0.10,
    "query_match": 0.15,
    "name_match": 0.15,
    "email_match": 0.15,
    "submitted": 0.25,
    "screen_match": 0.10,
    "no_forbidden_action": 0.05,
    "finish_after_success": 0.05,
}

DEFAULT_RIDE_REWARD_WEIGHTS: dict[str, float] = {
    "episode_id": 0.02,
    "ride_pickup": 0.08,
    "ride_drop": 0.08,
    "selected_ride": 0.10,
    "screen": 0.20,
    "ride_confirmed": 0.52,
    "ride_cancelled": 0.52,
}

DEFAULT_FORM_RANDOMIZATION: dict[str, Any] = {
    "enabled": False,
    "button_text_variant": False,
    "field_order_variant": False,
    "theme_variant": False,
    "start_screen_variant": False,
    "network_delay_ms": [0, 0],
}

DEFAULT_RIDE_RANDOMIZATION: dict[str, Any] = {
    "enabled": False,
    "coupon_popup_probability": 0.0,
    "no_driver_probability": 0.0,
    "network_delay_ms": [0, 0],
}

DEFAULT_SAFETY: dict[str, Any] = {
    "forbid_payment": True,
    "forbid_messages": True,
    "forbid_account_changes": True,
}


@dataclass(frozen=True)
class MobileTask:
    task_id: str
    app: str
    surface: str
    instruction: str
    start_screen: str
    max_steps: int
    seed: int
    difficulty: str
    split: str
    expected_state: dict[str, Any]
    randomization: dict[str, Any]
    safety: dict[str, Any]
    reward_weights: dict[str, float]


def load_tasks(path: str | Path, split: str | None = None) -> list[MobileTask]:
    tasks: list[MobileTask] = []
    source = Path(path)
    task_split = split or _infer_split(source)
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            tasks.append(
                MobileTask(
                    task_id=raw["task_id"],
                    app=raw["app"],
                    surface=str(raw.get("surface", "android_apk")),
                    instruction=raw["instruction"],
                    start_screen=raw.get("start_screen", "home"),
                    max_steps=int(raw.get("max_steps", 15)),
                    seed=int(raw.get("seed", 0)),
                    difficulty=str(raw.get("difficulty", "easy")),
                    split=task_split,
                    expected_state=_normalize_expected_state(raw),
                    randomization=_normalize_randomization(raw),
                    safety={**DEFAULT_SAFETY, **dict(raw.get("safety", {}))},
                    reward_weights=_normalize_reward_weights(raw),
                )
            )
    return tasks


def _infer_split(path: Path) -> str:
    stem = path.stem
    if stem.endswith("_eval_randomized"):
        return "eval_randomized"
    if stem.endswith("_train"):
        return "train"
    if stem.endswith("_eval"):
        return "eval"
    return stem


def _normalize_expected_state(raw: dict[str, Any]) -> dict[str, Any]:
    expected_state = dict(raw.get("expected_state", {}))
    if raw.get("app") in {"form", "dummy_apk"} and "screen" not in expected_state:
        expected_state["screen"] = "submitted"
    return expected_state


def _normalize_randomization(raw: dict[str, Any]) -> dict[str, Any]:
    defaults = DEFAULT_FORM_RANDOMIZATION if raw.get("app") in {"form", "dummy_apk"} else DEFAULT_RIDE_RANDOMIZATION
    raw_randomization = dict(raw.get("randomization", {}))
    randomization = {**defaults, **raw_randomization}
    if "enabled" not in raw_randomization:
        randomization["enabled"] = any(
            value not in (False, 0, 0.0, None, "")
            and value != [0, 0]
            for key, value in randomization.items()
            if key != "enabled"
        )
    return randomization


def _normalize_reward_weights(raw: dict[str, Any]) -> dict[str, float]:
    reward_weights = dict(raw.get("reward_weights", {}))
    if raw.get("app") in {"form", "dummy_apk"}:
        return {**DEFAULT_FORM_REWARD_WEIGHTS, **{key: float(value) for key, value in reward_weights.items()}}
    return {key: float(value) for key, value in reward_weights.items()}
