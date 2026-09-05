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

@verifier("T1", 1)
def pickup_from_preferences(c):
    """T1: assess the complete policy using strategy 1."""
    return field_check(c, "T1", 0)


@verifier("T1", 2)
def pickup_from_accessibility(c):
    """T1: assess the complete policy using strategy 2."""
    return field_check(c, "T1", 1)


@verifier("T1", 3)
def pickup_from_screenshot(c):
    """T1: assess the complete policy using strategy 3."""
    return field_check(c, "T1", 2)


@verifier("T1", 4)
def pickup_from_mutations(c):
    """T1: assess the complete policy using strategy 4."""
    return field_check(c, "T1", 3)


@verifier("T1", 5)
def pickup_from_runtime(c):
    """T1: assess the complete policy using strategy 5."""
    return field_check(c, "T1", 4)


@verifier("T2", 1)
def ride_type_from_preferences(c):
    """T2: assess the complete policy using strategy 1."""
    return field_check(c, "T2", 0)


@verifier("T2", 2)
def ride_type_from_accessibility(c):
    """T2: assess the complete policy using strategy 2."""
    return field_check(c, "T2", 1)


@verifier("T2", 3)
def ride_type_from_screenshot(c):
    """T2: assess the complete policy using strategy 3."""
    return field_check(c, "T2", 2)


@verifier("T2", 4)
def ride_type_from_mutations(c):
    """T2: assess the complete policy using strategy 4."""
    return field_check(c, "T2", 3)


@verifier("T2", 5)
def ride_type_from_runtime(c):
    """T2: assess the complete policy using strategy 5."""
    return field_check(c, "T2", 4)


@verifier("T3", 1)
def destination_from_preferences(c):
    """T3: assess the complete policy using strategy 1."""
    return field_check(c, "T3", 0)


@verifier("T3", 2)
def destination_from_accessibility(c):
    """T3: assess the complete policy using strategy 2."""
    return field_check(c, "T3", 1)


@verifier("T3", 3)
def destination_from_screenshot(c):
    """T3: assess the complete policy using strategy 3."""
    return field_check(c, "T3", 2)


@verifier("T3", 4)
def destination_from_mutations(c):
    """T3: assess the complete policy using strategy 4."""
    return field_check(c, "T3", 3)


@verifier("T3", 5)
def destination_from_runtime(c):
    """T3: assess the complete policy using strategy 5."""
    return field_check(c, "T3", 4)


@verifier("T4", 1)
def cab_from_preferences(c):
    """T4: assess the complete policy using strategy 1."""
    return field_check(c, "T4", 0)


@verifier("T4", 2)
def cab_from_accessibility(c):
    """T4: assess the complete policy using strategy 2."""
    return field_check(c, "T4", 1)


@verifier("T4", 3)
def cab_from_screenshot(c):
    """T4: assess the complete policy using strategy 3."""
    return field_check(c, "T4", 2)


@verifier("T4", 4)
def cab_from_mutations(c):
    """T4: assess the complete policy using strategy 4."""
    return field_check(c, "T4", 3)


@verifier("T4", 5)
def cab_from_runtime(c):
    """T4: assess the complete policy using strategy 5."""
    return field_check(c, "T4", 4)


@verifier("T5", 1)
def payment_from_preferences(c):
    """T5: assess the complete policy using strategy 1."""
    return field_check(c, "T5", 0)


@verifier("T5", 2)
def payment_from_accessibility(c):
    """T5: assess the complete policy using strategy 2."""
    return field_check(c, "T5", 1)


@verifier("T5", 3)
def payment_from_screenshot(c):
    """T5: assess the complete policy using strategy 3."""
    return field_check(c, "T5", 2)


@verifier("T5", 4)
def payment_from_mutations(c):
    """T5: assess the complete policy using strategy 4."""
    return field_check(c, "T5", 3)


@verifier("T5", 5)
def payment_from_runtime(c):
    """T5: assess the complete policy using strategy 5."""
    return field_check(c, "T5", 4)


@verifier("T6", 1)
def booking_from_preferences(c):
    """T6: assess the complete policy using strategy 1."""
    return field_check(c, "T6", 0)


@verifier("T6", 2)
def booking_from_accessibility(c):
    """T6: assess the complete policy using strategy 2."""
    return field_check(c, "T6", 1)


@verifier("T6", 3)
def booking_from_screenshot(c):
    """T6: assess the complete policy using strategy 3."""
    return field_check(c, "T6", 2)


@verifier("T6", 4)
def booking_from_mutations(c):
    """T6: assess the complete policy using strategy 4."""
    return field_check(c, "T6", 3)


@verifier("T6", 5)
def booking_from_runtime(c):
    """T6: assess the complete policy using strategy 5."""
    return field_check(c, "T6", 4)


@verifier("T7", 1)
def contract_from_receipts(c):
    """T7: assess the complete policy using strategy 1."""
    return _ok(_strict_contract(c))


@verifier("T7", 2)
def contract_from_action_replay(c):
    """T7: assess the complete policy using strategy 2."""
    if not _strict_contract(c): return _ok(False)
    for before, after in action_pairs(c):
        if not _manual_action(raw_action(after)) or action_type(raw_action(after)) not in c["registry"]["interaction"]["permitted_actions"]:
            return _ok(False)
    return _ok()


@verifier("T7", 3)
def contract_from_mutations(c):
    """T7: assess the complete policy using strategy 3."""
    if not _strict_contract(c): return _ok(False)
    replay(frames(c)[-1], c)
    return _ok(all(e.get("accepted") is True for e in frames(c)[-1]["mutations"]))


@verifier("T7", 4)
def contract_from_runtime_history(c):
    """T7: assess the complete policy using strategy 4."""
    if not _strict_contract(c): return _ok(False)
    for frame in frames(c):
        if runtime(frame, c).get("sequence_error") != "false": return _ok(False)
    return _ok()


@verifier("T7", 5)
def contract_from_transport_audit(c):
    """T7: assess the complete policy using strategy 5."""
    if not _strict_contract(c): return _ok(False)
    for before, after in action_pairs(c):
        _require(isinstance(after.get("adb_events"), list), "TRANSPORT_AUDIT_MISSING")
        if any("KEYCODE_HOME" in e.get("args", []) for e in after["adb_events"] if e.get("phase") == "action"):
            return _ok(False)
    return _ok()
