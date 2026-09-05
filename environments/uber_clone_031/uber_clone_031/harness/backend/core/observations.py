"""Observation builders for compact, full, and screenshot modes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

ObservationMode = Literal["compact_text", "full_ui_tree", "screenshot_only", "hybrid", "screenshot_ui_tree"]


def build_observation(
    raw: dict[str, Any],
    mode: ObservationMode = "compact_text",
    screenshot_path: str | Path | None = None,
    ui_tree_xml: str | None = None,
) -> dict[str, Any]:
    elements = [_compact_element(node) for node in raw.get("ui", [])]
    observation: dict[str, Any] = {
        "schema_version": "mobile_observation.v1",
        "backend": raw.get("backend", "adb"),
        "task": raw.get("goal") or raw.get("task"),
        "task_id": raw.get("task_id"),
        "episode_id": raw.get("episode_id"),
        "screen": raw.get("screen", "unknown"),
        "step": raw.get("step", raw.get("steps", 0)),
        "steps": raw.get("steps", raw.get("step", 0)),
        "max_steps": raw.get("max_steps"),
        "elements": elements,
        "last_action": raw.get("last_action"),
        "last_error": raw.get("last_error"),
        "reward": raw.get("reward"),
        "final_reward": raw.get("final_reward"),
        "exact_success": raw.get("exact_success", raw.get("final_reward", 0.0) >= 1.0),
        "reward_components": raw.get("reward_components", {}),
        "reset_metadata": raw.get("reset_metadata"),
    }
    if mode in {"full_ui_tree", "hybrid", "screenshot_ui_tree"}:
        observation["ui"] = raw.get("ui", [])
        observation["ui_tree_xml"] = ui_tree_xml or raw.get("ui_tree_xml")
    if mode in {"screenshot_only", "hybrid", "screenshot_ui_tree"}:
        observation["screenshot_path"] = str(screenshot_path) if screenshot_path else raw.get("screenshot_path")
    if mode == "screenshot_only":
        observation["action_history"] = raw.get("action_history", [])
    return observation


def _compact_element(node: dict[str, Any]) -> dict[str, Any]:
    element_id = node.get("id") or _local_resource_name(node.get("resource_id"))
    return {
        "element_index": node.get("element_index"),
        "element_id": element_id,
        "text": node.get("text", ""),
        "role": node.get("class_name", node.get("role", "")),
        "clickable": bool(node.get("clickable", True)),
        "focused": bool(node.get("focused", False)),
        "bounds": node.get("bounds"),
    }


def _local_resource_name(raw: str | None) -> str | None:
    if not raw:
        return None
    if "/" in raw:
        return raw.rsplit("/", 1)[-1]
    return raw
