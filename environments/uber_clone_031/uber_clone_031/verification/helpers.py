from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from functools import wraps
import jsonschema
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.verification.evidence_readers import Unassessable, accessibility, action_pairs, action_type, artifact_bytes, field_check, frames, prefs, raw_action, replay, runtime, target_id, ui_root
from uber_clone_031.verification.scoring import REWARDS


def _ok(value=True, reason="POLICY_CONFIRMED"):
    return bool(value), reason if value else "POLICY_VIOLATED", value, True


def _require(condition, reason):
    if not condition: raise Unassessable(reason)


def _full_readiness(c):
    registry, capabilities = c["registry"], c.get("capabilities", {})
    _require(c.get("registry_valid") is True, "REGISTRY_UNUSABLE")
    _require(c.get("task_expected") == registry["task"]["expected"], "YAML_JSON_TASK_MISMATCH")
    _require(c.get("task_id") == registry["task"]["task_id"], "TASK_ID_MISMATCH")
    _require(c.get("max_steps") == registry["task"]["max_steps"], "STEP_BUDGET_MISMATCH")
    for name in registry["validity"]["required_capabilities"]:
        _require(capabilities.get(name) is True, "CAPABILITY_UNAVAILABLE:" + name)
    installed = c.get("installed_apk") or {}
    _require(installed.get("package") == registry["app"]["package"] and bool(installed.get("sha256")), "INSTALLED_APP_UNIDENTIFIED")
    _require(c.get("expected_apk_sha256") == installed.get("sha256"), "INSTALLED_APK_NOT_BUILD_MATCHED")
    _require(runtime(frames(c)[0], c).get("contract_version") == registry["app"]["contract_version"], "INCOMPATIBLE_APP")
    return True


def _schema_action(value):
    try: MobileAction.parse_json(value); return True
    except (ActionValidationError, TypeError, ValueError, AttributeError): return False


def _manual_action(value):
    if not isinstance(value, dict): return False
    kind = action_type(value)
    if kind not in {"tap_element", "type_text", "tap_coordinates", "press_back", "press_home", "swipe", "wait", "finish"}:
        return False
    target = value.get("element_id", value.get("target"))
    if target is not None and not isinstance(target, str): return False
    if kind in {"tap_element", "type_text"} and not target: return False
    if kind == "type_text" and not isinstance(value.get("text"), str): return False
    if value.get("text") is not None and not isinstance(value.get("text"), str): return False
    if kind in {"press_back", "press_home", "wait", "finish"} and target is not None: return False
    numeric = ("x", "y", "x1", "y1", "x2", "y2", "duration_ms")
    if any(value.get(k) is not None and type(value[k]) is not int for k in numeric): return False
    required = ("x", "y") if kind == "tap_coordinates" else ("x1", "y1", "x2", "y2") if kind == "swipe" else ()
    return all(type(value.get(k)) is int for k in required)


def _jsonschema_action(value):
    if not isinstance(value, dict): return False
    action = dict(value)
    action["type"] = action_type(value)
    if "element_id" not in action and "target" in action: action["element_id"] = action["target"]
    schema = {"type": "object", "required": ["type"], "properties": {
        "type": {"enum": ["tap_element", "type_text", "tap_coordinates", "press_back", "press_home", "swipe", "wait", "finish"]},
        "element_id": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]},
        **{k: {"type": ["integer", "null"]} for k in ("x", "y", "x1", "y1", "x2", "y2", "duration_ms")}}}
    if list(jsonschema.Draft202012Validator(schema).iter_errors(action)): return False
    return _manual_action(action)


def _scan(c, check):
    unavailable = []
    for before, after in action_pairs(c):
        try:
            if check(before, after) is False:
                return False, "ACTION_POLICY_VIOLATION", after["index"], "all applicable actions comply"
        except Unassessable as exc:
            unavailable.append(str(exc))
    if unavailable: raise Unassessable(";".join(sorted(set(unavailable))))
    return _ok()


def _action_receipt(frame):
    result = frame.get("info")
    _require(isinstance(result, dict) and type(result.get("action_executed")) is bool, "ACTION_RECEIPT_UNAVAILABLE")
    return result


def _target_xml(before, after, c):
    action = raw_action(after)
    if action_type(action) not in {"tap_element", "type_text"}: return True
    wanted = target_id(action)
    node = next((e for e in ui_root(before, c).iter("node")
                 if e.get("resource-id") == c["registry"]["app"]["package"] + ":id/" + str(wanted)), None)
    if node is None: return False
    bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    area = bounds is not None and int(bounds[3]) > int(bounds[1]) and int(bounds[4]) > int(bounds[2])
    return bool(area and node.get("enabled") == "true" and
                (node.get("clickable") == "true" or node.get("class", "").endswith("EditText")))


def _execution(before, after):
    receipt = _action_receipt(after)
    if receipt.get("failure_origin") == "pipeline" or receipt.get("execution_errors"):
        raise Unassessable("TRANSPORT_OR_HARNESS_EXECUTION_UNASSESSABLE")
    return receipt["action_executed"]


def _semantic(before, after, c):
    action = raw_action(after)
    kind, target = action_type(action), target_id(action)
    if kind not in {"tap_element", "type_text"}: return True
    _require(isinstance(target, str), "SEMANTIC_TARGET_UNRESOLVED")
    semantic = {v: k for k, v in c["registry"]["ui"]["semantic_targets"].items()}.get(target)
    if semantic is None: return False
    expected = c["registry"]["task"]["expected"]
    for prefix, parameter in (("ride_type.", "ride_type"), ("cab.", "cab_type"), ("payment.", "payment_method")):
        if semantic.startswith(prefix):
            return semantic.split(".", 1)[1].casefold() == expected[parameter].casefold()
    if semantic == "destination.airport": return expected["destination"] == "Airport"
    if semantic == "destination.city_center": return expected["destination"] == "City Center"
    if semantic == "booking.cancel": return expected["cancel_after_assignment"]
    return semantic in {"pickup.input", "destination.input", "destination.search", "booking.confirm"}


def _semantic_effect(before, after, c, reader):
    if not _semantic(before, after, c): return False
    action = raw_action(after)
    semantic = {v:k for k,v in c["registry"]["ui"]["semantic_targets"].items()}.get(target_id(action), "")
    fields = {"ride_type": "ride_type", "cab": "selected_ride", "payment": "payment"}
    prefix, _, selected = semantic.partition(".")
    if prefix not in fields or _action_receipt(after).get("stage_transition_accepted") is not True:
        return True
    state = reader(after, c)
    field = fields[prefix]
    _require(field in state, "SEMANTIC_EFFECT_STATE_UNAVAILABLE")
    return str(state[field]).casefold() == selected.casefold()


def _strict_contract(c):
    # The app remains recoverable, but the user's new T7 policy retains hard
    # no-invalid-action and no-forbidden-action requirements for this benchmark.
    for before, after in action_pairs(c):
        receipt = _action_receipt(after)
        if receipt.get("failure_origin") == "pipeline" or receipt.get("execution_errors"):
            raise Unassessable("CONTRACT_RECEIPT_UNASSESSABLE")
        if receipt.get("schema_valid") is False or receipt.get("permission_granted") is False:
            return False
        if not receipt["action_executed"] or receipt.get("stage_transition_accepted") is False:
            return False
        if after["observation"]["steps"] > c["max_steps"]: return False
        state = prefs(after, c)
        if state.get("sequence_error") != "false": return False
    final = prefs(frames(c)[-1], c)
    _require("sequence_error" in final, "SEQUENCE_STATE_UNAVAILABLE")
    return final["sequence_error"] == "false" and frames(c)[-1]["observation"]["steps"] <= c["max_steps"]


def _integrity(c):
    count = 0
    for frame in frames(c):
        prefs(frame, c)
        if frame.get("is_action", frame.get("info") is not None):
            count += 1
            _action_receipt(frame)
        _require(frame.get("observation", {}).get("steps") == count, "ACTION_FRAME_COUNT_MISMATCH")
        _require(not frame.get("observation", {}).get("ui_error"), "UI_CAPTURE_ERROR")
    return True
