"""Six independently reported task stages; booking success is a separate metric."""
from __future__ import annotations

import xml.etree.ElementTree as ET

RUBRIC_VERSION = "ride-stages-v2"
STAGES = (
    ("pickup", "Correct pickup entered", "ride_pickup", 0, ()),
    ("ride_type", "Correct ride type selected", "ride_type", 1, ()),
    ("destination", "Correct destination searched", "ride_drop", 2, ("ride_type",)),
    ("cab", "Correct cab selected", "selected_ride", 3, ("destination",)),
    ("payment", "Correct payment selected", "payment", 4, ("cab",)),
    ("booking", "Correct booking confirmed", None, 5, ("pickup", "ride_type", "destination", "cab", "payment")),
)


def parse_state(xml: str) -> dict[str, str]:
    """Fail closed on malformed, duplicate, or unsupported preference values."""
    try:
        root = ET.fromstring(xml)
        if root.tag != "map":
            return {}
        state = {}
        for node in root:
            name = node.get("name")
            if not name or name in state or node.tag not in {"string", "boolean", "int", "long"}:
                return {}
            state[name] = (node.text or "") if node.tag == "string" else node.get("value", "")
        return state
    except (ET.ParseError, TypeError):
        return {}


def action_stage(action):
    if not isinstance(action, dict):
        return None
    target = str(action.get("element_id") or action.get("target") or "").rsplit("/", 1)[-1]
    if target == "pickup_input": return "pickup"
    if target.startswith("ride_type_"): return "ride_type"
    if target in {"drop_input", "destination_search_button", "location_suggestion_1", "location_suggestion_2"}: return "destination"
    if target.startswith("ride_option_"): return "cab"
    if target.startswith("payment_"): return "payment"
    if target in {"confirm_ride_button", "cancel_ride_button"}: return "booking"
    return None


def verify(task, xml: str, *, steps: int, invalid: bool = False, forbidden: bool = False,
           execution_errors: list[str] | None = None, evidence_ok: bool = True,
           previous: dict | None = None, action=None, action_info: dict | None = None) -> dict:
    """Unweighted coverage = completed task stages / 6, not a calibrated utility.

    State predicates are independently evaluated (a wrong pickup does not hide
    a correct payment). Native stage prerequisites prove that a selection was
    committed. Booking still requires every expected field and current episode.
    Historical rejected actions remain diagnostics, not permanent failure gates.
    """
    actual, expected = parse_state(xml), task.expected_state()
    errors = list(execution_errors or [])
    integrity = {"state_present": bool(actual),
                 "current_episode": bool(task.episode_id) and actual.get("episode_id") == task.episode_id}
    trusted = all(integrity.values())
    try:
        native_stage = int(actual.get("journey_stage", "-1"))
    except (TypeError, ValueError):
        native_stage = -1
    integrity["valid_native_stage"] = 0 <= native_stage <= 5
    trusted = trusted and integrity["valid_native_stage"]
    outcome = {k: k in actual and actual[k] == v for k, v in expected.items() if k != "episode_id"}
    outcome["not_cancelled"] = actual.get("ride_cancelled") == ("true" if task.cancel_after_assignment else "false")
    outcome_success = trusted and bool(outcome) and all(outcome.values())
    process = {"no_invalid_action": not invalid, "no_forbidden_action": not forbidden,
               "sequence_clean": actual.get("sequence_error") == "false",
               "within_step_budget": 0 <= steps <= task.max_steps}
    execution = {"no_execution_error": not errors, "evidence_complete": evidence_ok}
    evaluation_valid = trusted and all(execution.values()) and process["within_step_budget"]
    safe_success = outcome_success and evaluation_valid and process["no_forbidden_action"]
    previous_stages = (previous or {}).get("stages", {})
    info, attempted = action_info or {}, action_stage(action)
    checks = {}
    for name, label, field, minimum, dependencies in STAGES:
        complete = outcome_success if field is None else (
            trusted and native_stage >= minimum and field in actual and actual[field] == expected[field])
        old = previous_stages.get(name, {})
        eligible = trusted and (name in {"pickup", "ride_type"} or native_stage >= minimum - 1)
        if name == "booking":
            eligible = eligible and bool(actual.get("ride_pickup"))
        status = "completed" if complete else "not_reached"
        if not complete:
            if old.get("completed"): status = "invalidated"
            elif attempted == name and info.get("stage_transition_accepted") is False:
                status = "rejected"
            elif eligible and field and actual.get(field):
                status = "in_progress" if native_stage < minimum else "mismatch"
            elif eligible: status = "ready"
        checks[name] = {"label": label, "completed": bool(complete), "status": status,
                        "eligible": bool(eligible), "depends_on": list(dependencies),
                        "ever_completed": bool(complete or old.get("ever_completed")),
                        "first_completed_step": old.get("first_completed_step", steps if complete else None),
                        "field": field, "expected": expected.get(field) if field else "confirmed matching booking",
                        "actual": actual.get(field) if field else actual.get("screen"),
                        "rejection_reason": info.get("rejection_reason") if attempted == name else None}
        if complete and checks[name]["first_completed_step"] is None:
            checks[name]["first_completed_step"] = steps
    count = sum(item["completed"] for item in checks.values())
    progress = count / len(STAGES)
    return {"rubric_version": RUBRIC_VERSION, "stages": checks, "completed_stages": count,
            "total_stages": len(STAGES), "progress_fraction": progress, "reward": progress,
            "final_reward": float(safe_success), "task_success": outcome_success,
            "outcome_success": outcome_success, "safe_success": safe_success,
            "evaluation_valid": evaluation_valid, "outcome": outcome, "integrity": integrity,
            "process": process, "execution": execution, "execution_errors": errors,
            "expected_state": expected, "actual_state": actual}
