from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from functools import wraps
from uber_clone_031.verification.contracts import VERIFIERS
import jsonschema
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.verification.evidence_readers import Unassessable, accessibility, action_pairs, action_type, artifact_bytes, field_check, frames, prefs, raw_action, replay, runtime, target_id, ui_root
from uber_clone_031.verification.scoring import REWARDS

from uber_clone_031.verification.contracts import verifier
from uber_clone_031.verification.helpers import _ok, _require, _full_readiness, _schema_action, _manual_action, _jsonschema_action, _scan, _action_receipt, _target_xml, _execution, _semantic, _semantic_effect, _strict_contract, _integrity

@verifier("V1", 1)
def schema_and_capabilities(c):
    """V1: assess the complete policy using strategy 1."""
    _full_readiness(c)
    return _ok(len(c["registry"]["policies"]) == 14)


@verifier("V1", 2)
def yaml_and_capability_receipts(c):
    """V1: assess the complete policy using strategy 2."""
    _full_readiness(c)
    _require(c.get("capability_receipts"), "CAPABILITY_RECEIPTS_MISSING")
    _require(all(r.get("returncode") == 0 for r in c["capability_receipts"]), "CAPABILITY_COMMAND_FAILED")
    return _ok(c["task_expected"] == c["registry"]["task"]["expected"])


@verifier("V1", 3)
def registry_and_live_contract(c):
    """V1: assess the complete policy using strategy 3."""
    _full_readiness(c)
    required = {v["implementation"] for p in c["registry"]["policies"] for v in p["verifiers"]}
    _require(len(required) == 70 and required <= set(VERIFIERS), "INCOMPLETE_IMPLEMENTATION_REGISTRY")
    return _ok()


@verifier("V1", 4)
def installed_app_and_tools(c):
    """V1: assess the complete policy using strategy 4."""
    _full_readiness(c)
    _require(re.fullmatch(r"[0-9a-f]{64}", c["installed_apk"]["sha256"]), "APK_HASH_INVALID")
    _require(c.get("capability_receipts"), "CAPABILITY_RECEIPTS_MISSING")
    return _ok(c["installed_apk"]["package"] == c["registry"]["app"]["package"])


@verifier("V1", 5)
def runtime_schema_and_capabilities(c):
    """V1: assess the complete policy using strategy 5."""
    _full_readiness(c)
    state = runtime(frames(c)[0], c)
    _require(set(c["registry"]["state"]["fields"]) <= set(state), "RUNTIME_FIELDS_INCOMPLETE")
    return _ok()


@verifier("V2", 1)
def preference_episode_chain(c):
    """V2: assess the complete policy using strategy 1."""
    _integrity(c)
    for frame in frames(c): prefs(frame, c)
    return _ok()


@verifier("V2", 2)
def artifact_hash_chain(c):
    """V2: assess the complete policy using strategy 2."""
    _integrity(c)
    for frame in frames(c):
        artifact_bytes(c, frame.get("state")); artifact_bytes(c, frame.get("ui"))
    return _ok()


@verifier("V2", 3)
def mutation_episode_chain(c):
    """V2: assess the complete policy using strategy 3."""
    _integrity(c)
    for frame in frames(c): replay(frame, c)
    return _ok()


@verifier("V2", 4)
def runtime_snapshot_chain(c):
    """V2: assess the complete policy using strategy 4."""
    _integrity(c)
    for frame in frames(c):
        state = runtime(frame, c)
        _require(state.get("ride_action_sequence") == str(frame.get("app_sequence")), "RUNTIME_SNAPSHOT_SEQUENCE_MISMATCH")
    return _ok()


@verifier("V2", 5)
def capture_and_receipt_alignment(c):
    """V2: assess the complete policy using strategy 5."""
    _integrity(c)
    for frame in frames(c):
        _require(frame.get("time") and isinstance(frame.get("adb_events"), list), "CAPTURE_RECEIPTS_MISSING")
        _require(frame.get("observation", {}).get("observation_freshness", {}).get("fresh") is True, "STALE_UI_RECEIPT")
    return _ok()
