"""Rollout labeling and failure categorization."""

from __future__ import annotations

from typing import Any


def analyze_rollout(rollout: dict[str, Any]) -> dict[str, Any]:
    final = rollout.get("final_observation", {})
    transitions = rollout.get("transitions", [])
    invalid_action_count = sum(1 for item in transitions if item.get("info", {}).get("error") == "invalid_action_schema")
    safety_block_count = sum(1 for item in transitions if item.get("info", {}).get("error") == "destructive_action")
    adb_error_count = sum(
        1
        for item in transitions
        if "RuntimeError" in str(item.get("info", {}).get("error", "")) or "LookupError" in str(item.get("info", {}).get("error", ""))
    )
    exact_success = bool(final.get("exact_success") or rollout.get("success"))
    failure_category = classify_failure(rollout, invalid_action_count, safety_block_count, adb_error_count)
    trajectory_quality = classify_quality(exact_success, final.get("reward", 0.0), failure_category)
    usable_for_rl = failure_category not in {"unsafe"}
    return {
        "trajectory_quality": trajectory_quality,
        "failure_category": failure_category,
        "usable_for_rl": usable_for_rl,
        "usable_for_rollout_run": exact_success,
        "invalid_action_count": invalid_action_count,
        "safety_block_count": safety_block_count,
        "adb_error_count": adb_error_count,
        "stale_episode_rejection_count": int(
            bool(final.get("reward_components", {}).get("episode_match") is False and final.get("apk_state"))
        ),
    }


def classify_quality(exact_success: bool, reward: Any, failure_category: str) -> str:
    if exact_success:
        return "success"
    if failure_category == "unsafe":
        return "unsafe"
    if failure_category == "invalid_json":
        return "invalid"
    if failure_category == "adb_error":
        return "adb_error"
    if float(reward or 0.0) > 0.0:
        return "partial"
    return "failure"


def classify_failure(
    rollout: dict[str, Any],
    invalid_action_count: int,
    safety_block_count: int,
    adb_error_count: int,
) -> str:
    final = rollout.get("final_observation", {})
    last_error = str(final.get("last_error") or "")
    if invalid_action_count:
        return "invalid_json"
    if safety_block_count:
        return "safety_block"
    if adb_error_count:
        return "adb_error"
    if final.get("done") and not final.get("exact_success") and final.get("steps", 0) >= final.get("max_steps", 0):
        return "timeout"
    if "unsupported target" in last_error or "tap_unknown_element_id" in last_error:
        return "wrong_element"
    if "input_resource requires text" in last_error:
        return "wrong_text"
    if final.get("reward_components", {}).get("episode_match") is False:
        return "reward_mismatch"
    return "none"
