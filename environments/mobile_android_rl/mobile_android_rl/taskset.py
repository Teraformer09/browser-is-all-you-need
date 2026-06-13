"""Taskset loader for mobile Android RL tasks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from android_adk_rl_env.core.task import MobileTask, load_tasks


@dataclass(frozen=True)
class MobileAndroidTaskset:
    split: str
    tasks: list[MobileTask]

    def __len__(self) -> int:
        return len(self.tasks)


def load_taskset(split: str = "eval", app: str = "form", **kwargs: object) -> MobileAndroidTaskset:
    del kwargs
    root = Path(__file__).resolve().parent / "tasks"
    filename = f"{app}_{split}.jsonl"
    path = root / filename
    if not path.exists():
        raise FileNotFoundError(f"taskset not found: {path}")
    return MobileAndroidTaskset(split=split, tasks=load_tasks(path, split=split))
