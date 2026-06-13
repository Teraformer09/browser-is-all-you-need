"""Replay buffer helpers for successful and near-miss mobile trajectories."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReplayBuffer:
    success_rows: list[dict[str, Any]] = field(default_factory=list)
    near_miss_rows: list[dict[str, Any]] = field(default_factory=list)
    failure_rows: list[dict[str, Any]] = field(default_factory=list)

    def add(self, rollout: dict[str, Any]) -> None:
        quality = rollout.get("trajectory_quality")
        if quality == "success":
            self.success_rows.append(rollout)
        elif quality == "partial":
            self.near_miss_rows.append(rollout)
        else:
            self.failure_rows.append(rollout)

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "success": self.success_rows,
                    "near_miss": self.near_miss_rows,
                    "failure": self.failure_rows,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
