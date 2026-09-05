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

@verifier("S1", 1)
def resource_semantic_map(c):
    """S1: assess the complete policy using strategy 1."""
    return _scan(c, lambda b, a: _semantic(b, a, c))


@verifier("S1", 2)
def declared_operation_lookup(c):
    """S1: assess the complete policy using strategy 2."""
    def check(before, after):
        value = raw_action(after)
        if action_type(value) in {"tap_element", "type_text"}:
            _require(c["registry"]["ui"].get("semantic_targets"), "SEMANTIC_MAP_UNAVAILABLE")
        return _semantic(before, after, c)
    return _scan(c, check)


@verifier("S1", 3)
def post_state_semantic_effect(c):
    """S1: assess the complete policy using strategy 3."""
    def check(before, after):
        return _semantic_effect(before, after, c, prefs)
    return _scan(c, check)


@verifier("S1", 4)
def mutation_semantic_replay(c):
    """S1: assess the complete policy using strategy 4."""
    def check(before, after):
        return _semantic_effect(before, after, c, replay)
    return _scan(c, check)


@verifier("S1", 5)
def runtime_semantic_effect(c):
    """S1: assess the complete policy using strategy 5."""
    def check(before, after):
        return _semantic_effect(before, after, c, runtime)
    return _scan(c, check)
