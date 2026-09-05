"""YAML task-spec loading and task factory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from uber_clone_031.harness.backend.tasks.dummy_apk import DummyApkFormSearchTask
from uber_clone_031.harness.backend.tasks.ride_booking import RideBookingTask


@dataclass(frozen=True)
class AppSpec:
    package: str
    apk_path: str | None = None


@dataclass(frozen=True)
class SuccessSpec:
    type: str
    check: str
    threshold: float = 1.0


@dataclass(frozen=True)
class RewardSpec:
    mode: str = "binary"


@dataclass(frozen=True)
class EvalTaskSpec:
    task_id: str
    app: AppSpec
    setup: dict[str, Any]
    goal: str
    max_steps: int
    success: SuccessSpec
    reward: RewardSpec = field(default_factory=RewardSpec)
    task_type: str = "generic"
    benchmark_family: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    policy_hint: str | None = None
    tags: tuple[str, ...] = ()
    source_path: str | None = None

    @property
    def family_id(self) -> str:
        return self.benchmark_family or self.task_id


def load_task_spec(path: str | Path) -> EvalTaskSpec:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"task spec must be a mapping: {source}")

    app_raw = payload.get("app") or {}
    success_raw = payload.get("success") or {}
    reward_raw = payload.get("reward") or {}
    tags_raw = payload.get("tags") or []
    if not isinstance(tags_raw, list):
        raise ValueError(f"task spec tags must be a list: {source}")

    return EvalTaskSpec(
        task_id=str(payload["task_id"]),
        app=AppSpec(
            package=str(app_raw["package"]),
            apk_path=_optional_str(app_raw.get("apk_path")),
        ),
        setup=dict(payload.get("setup") or {}),
        goal=str(payload["goal"]),
        max_steps=int(payload.get("max_steps", 12)),
        success=SuccessSpec(
            type=str(success_raw.get("type", "registered_check")),
            check=str(success_raw["check"]),
            threshold=float(success_raw.get("threshold", 1.0)),
        ),
        reward=RewardSpec(mode=str(reward_raw.get("mode", "binary"))),
        task_type=str(payload.get("task_type", "generic")),
        benchmark_family=_optional_str(payload.get("benchmark_family")),
        parameters=dict(payload.get("parameters") or {}),
        policy_hint=_optional_str(payload.get("policy_hint")),
        tags=tuple(str(item) for item in tags_raw),
        source_path=str(source),
    )


def load_task_specs(paths: list[str | Path]) -> list[EvalTaskSpec]:
    return [load_task_spec(path) for path in paths]


def load_task_specs_from_dir(directory: str | Path) -> list[EvalTaskSpec]:
    root = Path(directory)
    return [load_task_spec(path) for path in sorted(root.glob("*.yaml"))]


def build_known_task(spec: EvalTaskSpec, *, attempt: int = 0) -> DummyApkFormSearchTask | RideBookingTask | None:
    params = dict(spec.parameters)
    seed = int(params.pop("seed", spec.setup.get("seed", 0) or 0)) + int(attempt)

    if spec.task_type == "dummy_form":
        return DummyApkFormSearchTask(
            task_id=spec.task_id,
            query=str(params.pop("query")),
            name=str(params.pop("name")),
            email=str(params.pop("email")),
            package=spec.app.package,
            max_steps=spec.max_steps,
            seed=seed,
            start_screen=str(spec.setup.get("start_screen", "home")),
            difficulty=str(spec.setup.get("difficulty", "easy")),
            randomization=dict(spec.setup.get("randomization") or {}),
            reward_weights=dict(spec.setup.get("reward_weights") or {}),
            safety=dict(spec.setup.get("safety") or {}),
        )
    if spec.task_type == "ride_booking":
        ride_type = str(params.pop("ride_type", params.pop("selected_ride_type", "Ride")))
        destination = str(params.pop("destination", params.pop("drop", "Noida City Centre")))
        return RideBookingTask(
            task_id=spec.task_id,
            pickup=str(params.pop("pickup", "Current location")),
            ride_type=ride_type,
            destination=destination,
            selected_ride=str(params.pop("selected_ride", params.pop("cab_type", "Mini"))),
            payment=str(params.pop("payment", "upi")),
            coupon=str(params.pop("coupon", "")),
            cancel_after_assignment=bool(params.pop("cancel_after_assignment", False)),
            package=spec.app.package,
            max_steps=spec.max_steps,
            seed=seed,
            reward_weights=dict(spec.setup.get("reward_weights") or {}),
        )
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
