"""Snapshot-aware task reset helpers."""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ResetMetadata:
    requested_mode: str
    applied_mode: str
    fallback_used: bool
    baseline_snapshot: str | None
    snapshot_created: bool
    duration_seconds: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reset_task_device(task: Any, device: Any) -> ResetMetadata:
    reset_mode = os.environ.get("RESET_MODE", "snapshot").strip().lower() or "snapshot"
    snapshot_name = os.environ.get("ADB_BASELINE_SNAPSHOT", f"{task.package.replace('.', '_')}_baseline")
    started = time.perf_counter()
    applied_mode = "full"
    fallback_used = False
    snapshot_created = False
    error: str | None = None

    try:
        if reset_mode == "snapshot" and _supports_snapshots(device):
            created = _ensure_snapshot(device, task, snapshot_name)
            if created:
                snapshot_created = True
                applied_mode = "full"
            else:
                try:
                    device.restore_snapshot(snapshot_name)
                    _launch_for_task(device, task)
                    applied_mode = "snapshot"
                except Exception as exc:  # noqa: BLE001
                    fallback_used = True
                    error = f"{type(exc).__name__}: {exc}"
                    _full_reset(device, task)
                    applied_mode = "full"
        else:
            _full_reset(device, task)
            applied_mode = "full"
            if reset_mode == "snapshot" and _supports_snapshots(device):
                snapshot_created = _maybe_create_snapshot(device, snapshot_name)
    except Exception:
        duration = max(0.0, time.perf_counter() - started)
        raise

    duration = max(0.0, time.perf_counter() - started)
    return ResetMetadata(
        requested_mode=reset_mode,
        applied_mode=applied_mode,
        fallback_used=fallback_used,
        baseline_snapshot=snapshot_name if _supports_snapshots(device) else None,
        snapshot_created=snapshot_created,
        duration_seconds=duration,
        error=error,
    )


def _supports_snapshots(device: Any) -> bool:
    return all(hasattr(device, name) for name in ("snapshot_exists", "save_snapshot", "restore_snapshot"))


def _ensure_snapshot(device: Any, task: Any, snapshot_name: str) -> bool:
    if device.snapshot_exists(snapshot_name):
        return False
    _full_reset(device, task)
    device.save_snapshot(snapshot_name)
    return True


def _maybe_create_snapshot(device: Any, snapshot_name: str) -> bool:
    if device.snapshot_exists(snapshot_name):
        return False
    device.save_snapshot(snapshot_name)
    return True


def _full_reset(device: Any, task: Any) -> None:
    if hasattr(device, "reset_app"):
        device.reset_app(episode_id=task.episode_id, extras=task.launch_extras())
        return
    device.wait_for_device()
    device.clear_app_data()
    try:
        device.launch_app(episode_id=task.episode_id, extras=task.launch_extras())
    except TypeError:
        if hasattr(device, "episode_id"):
            device.episode_id = task.episode_id
        device.launch_app()


def _launch_for_task(device: Any, task: Any) -> None:
    device.wait_for_device()
    try:
        device.launch_app(episode_id=task.episode_id, extras=task.launch_extras())
    except TypeError:
        if hasattr(device, "episode_id"):
            device.episode_id = task.episode_id
        device.launch_app()
    if hasattr(device, "wait_for_ui_ready"):
        device.wait_for_ui_ready()
