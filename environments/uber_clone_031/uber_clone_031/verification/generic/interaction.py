from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from functools import wraps
import jsonschema
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.verification.evidence_readers import Unassessable, accessibility, action_pairs, action_type, artifact_bytes, field_check, frames, prefs, raw_action, replay, runtime, target_id, ui_root
from uber_clone_031.verification.scoring import REWARDS

from uber_clone_031.verification.contracts import verifier
from uber_clone_031.verification.helpers import _ok, _require, _full_readiness, _schema_action, _manual_action, _jsonschema_action, _scan, _action_receipt, _target_xml, _execution, _semantic, _semantic_effect, _strict_contract, _integrity

@verifier("G1", 1)
def mobile_action_schema(c):
    """G1: assess the complete policy using strategy 1."""
    return _scan(c, lambda b, a: _schema_action(raw_action(a)))


@verifier("G1", 2)
def jsonschema_action_schema(c):
    """G1: assess the complete policy using strategy 2."""
    return _scan(c, lambda b, a: _jsonschema_action(raw_action(a)))


@verifier("G1", 3)
def manual_argument_contract(c):
    """G1: assess the complete policy using strategy 3."""
    return _scan(c, lambda b, a: _manual_action(raw_action(a)))


@verifier("G1", 4)
def canonical_roundtrip(c):
    """G1: assess the complete policy using strategy 4."""
    def check(before, after):
        value = raw_action(after)
        if not _schema_action(value): return False
        canonical = MobileAction.parse_json(value).to_dict()
        return _manual_action(canonical) and MobileAction.parse_json(canonical).to_dict() == canonical
    return _scan(c, check)


@verifier("G1", 5)
def receipt_schema_reconciliation(c):
    """G1: assess the complete policy using strategy 5."""
    def check(before, after):
        valid = _manual_action(raw_action(after))
        receipt = _action_receipt(after)
        _require(type(receipt.get("schema_valid")) is bool, "SCHEMA_RECEIPT_UNAVAILABLE")
        if not valid: return False
        _require(receipt["schema_valid"], "PARSER_DISAGREES_WITH_VALID_ACTION")
        return True
    return _scan(c, check)


@verifier("G2", 1)
def raw_tool_allowlist(c):
    """G2: assess the complete policy using strategy 1."""
    return _scan(c, lambda b, a: action_type(raw_action(a)) in c["registry"]["interaction"]["permitted_actions"])


@verifier("G2", 2)
def canonical_tool_allowlist(c):
    """G2: assess the complete policy using strategy 2."""
    def check(before, after):
        value = raw_action(after)
        if not _schema_action(value): return action_type(value) in c["registry"]["interaction"]["permitted_actions"]
        return MobileAction.parse_json(value).type in c["registry"]["interaction"]["permitted_actions"]
    return _scan(c, check)


@verifier("G2", 3)
def declarative_permission_rules(c):
    """G2: assess the complete policy using strategy 3."""
    def check(before, after):
        kind = action_type(raw_action(after))
        policy = c["registry"]["interaction"]
        _require(policy.get("permitted_actions") and policy.get("prohibited_actions"), "PERMISSION_POLICY_MISSING")
        return kind not in policy["prohibited_actions"] and kind in policy["permitted_actions"]
    return _scan(c, check)


@verifier("G2", 4)
def receipt_permission_audit(c):
    """G2: assess the complete policy using strategy 4."""
    def check(before, after):
        receipt = _action_receipt(after)
        _require(type(receipt.get("permission_granted")) is bool, "PERMISSION_RECEIPT_UNAVAILABLE")
        return receipt["permission_granted"] and action_type(raw_action(after)) in c["registry"]["interaction"]["permitted_actions"]
    return _scan(c, check)


@verifier("G2", 5)
def forbidden_trace_reconciliation(c):
    """G2: assess the complete policy using strategy 5."""
    def check(before, after):
        permitted = action_type(raw_action(after)) in c["registry"]["interaction"]["permitted_actions"]
        if not permitted: return False
        _require(isinstance(after.get("adb_events"), list), "ADB_TRACE_UNAVAILABLE")
        return not any("KEYCODE_HOME" in event.get("args", []) for event in after["adb_events"] if event.get("phase") == "action")
    return _scan(c, check)


@verifier("G3", 1)
def xml_target_interactability(c):
    """G3: assess the complete policy using strategy 1."""
    return _scan(c, lambda b, a: _target_xml(b, a, c))


@verifier("G3", 2)
def observation_target_interactability(c):
    """G3: assess the complete policy using strategy 2."""
    def check(before, after):
        action = raw_action(after)
        if action_type(action) not in {"tap_element", "type_text"}: return True
        ui_root(before, c)
        nodes = before["observation"].get("ui")
        _require(isinstance(nodes, list), "STRUCTURED_UI_MISSING")
        node = next((n for n in nodes if n.get("id") == target_id(action)), None)
        return bool(node and node.get("enabled") and (node.get("clickable") or str(node.get("class_name", "")).endswith("EditText")))
    return _scan(c, check)


@verifier("G3", 3)
def bounds_and_target_resolution(c):
    """G3: assess the complete policy using strategy 3."""
    def check(before, after):
        action = raw_action(after)
        if action_type(action) not in {"tap_element", "type_text"}: return True
        root = ui_root(before, c)
        candidates = [n for n in root.iter("node") if n.get("resource-id", "").rsplit("/", 1)[-1] == target_id(action)]
        if len(candidates) != 1: return False
        return _target_xml(before, after, c)
    return _scan(c, check)


@verifier("G3", 4)
def receipt_target_reconciliation(c):
    """G3: assess the complete policy using strategy 4."""
    def check(before, after):
        action = raw_action(after)
        if action_type(action) not in {"tap_element", "type_text"}: return True
        receipt = _action_receipt(after)
        _require(type(receipt.get("target_interactable")) is bool, "TARGET_RECEIPT_UNAVAILABLE")
        return receipt["target_interactable"] and _target_xml(before, after, c)
    return _scan(c, check)


@verifier("G3", 5)
def before_state_target_contract(c):
    """G3: assess the complete policy using strategy 5."""
    def check(before, after):
        if not _target_xml(before, after, c): return False
        action = raw_action(after)
        if action_type(action) not in {"tap_element", "type_text"}: return True
        target = target_id(action)
        semantic = {v:k for k,v in c["registry"]["ui"]["semantic_targets"].items()}.get(target)
        minimum = c["registry"]["actions"]["native_prerequisites"].get(semantic, 0)
        return int(prefs(before, c).get("journey_stage", "-1")) >= minimum
    return _scan(c, check)


@verifier("G4", 1)
def receipt_execution(c):
    """G4: assess the complete policy using strategy 1."""
    return _scan(c, _execution)


@verifier("G4", 2)
def adb_command_completion(c):
    """G4: assess the complete policy using strategy 2."""
    def check(before, after):
        if not _execution(before, after): return False
        events = after.get("adb_events")
        _require(isinstance(events, list), "ADB_TRACE_UNAVAILABLE")
        calls = [e for e in events if e.get("phase") == "action"]
        if action_type(raw_action(after)) not in {"wait", "finish"}:
            _require(bool(calls), "NO_ACTION_TRANSPORT_RECEIPT")
        _require(all(e.get("returncode") == 0 and not e.get("error") for e in calls), "ACTION_TRANSPORT_FAILED")
        return True
    return _scan(c, check)


@verifier("G4", 3)
def post_action_receipt_alignment(c):
    """G4: assess the complete policy using strategy 3."""
    def check(before, after):
        if not _execution(before, after): return False
        prefs(after, c); ui_root(after, c)
        _require(after["observation"]["steps"] == before["observation"]["steps"] + 1, "POST_ACTION_FRAME_MISMATCH")
        return True
    return _scan(c, check)


@verifier("G4", 4)
def execution_error_audit(c):
    """G4: assess the complete policy using strategy 4."""
    def check(before, after):
        result = _execution(before, after)
        receipt = _action_receipt(after)
        _require(not receipt.get("execution_errors"), "EXECUTION_ERRORS_RECORDED")
        return result
    return _scan(c, check)


@verifier("G4", 5)
def transport_and_effect_reconciliation(c):
    """G4: assess the complete policy using strategy 5."""
    def check(before, after):
        if not _execution(before, after): return False
        _require(type(_action_receipt(after).get("action_duration_ms")) in (float, int), "ACTION_TIMING_RECEIPT_MISSING")
        runtime(after, c)
        return True
    return _scan(c, check)
