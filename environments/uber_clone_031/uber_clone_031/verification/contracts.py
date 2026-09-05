from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from functools import wraps
import jsonschema
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.verification.evidence_readers import Unassessable, accessibility, action_pairs, action_type, artifact_bytes, field_check, frames, prefs, raw_action, replay, runtime, target_id, ui_root
from uber_clone_031.verification.scoring import REWARDS

VERIFIERS = {}

def verifier(policy, number):
    def bind(function):
        identifier = f"{policy}.V{number}"
        @wraps(function)
        def checked(context):
            last = max(0, len(context.get("frames") or []) - 1)
            sources = ("states", "ui", "screenshots", "mutations", "probes")
            extensions = ("xml", "xml", "png", "jsonl", "json")
            if policy in {"T1", "T2", "T3", "T4", "T5", "T6"}:
                refs = [f"{sources[number-1]}/{last:03d}.{extensions[number-1]}"]
            else:
                refs = [f"trajectory.jsonl#line={i+1}" for i in range(len(context.get("frames") or []))]
            refs.append(f"verifier_context.json#/registry/policies/{policy}")
            try:
                passed, reason, observed, expected = function(context)
                status = "PASS" if passed else "FAIL"
                return {"verifier_id": identifier, "status": status, "reward": REWARDS[status],
                        "reason_code": reason, "failure_origin": "none" if passed else "agent",
                        "observed_value": observed, "expected_value": expected, "evidence_refs": refs}
            except Unassessable as exc:
                return {"verifier_id": identifier, "status": "INVALID", "reward": 0,
                        "reason_code": str(exc), "failure_origin": "pipeline", "evidence_refs": refs}
            except Exception as exc:
                return {"verifier_id": identifier, "status": "INVALID", "reward": 0,
                        "reason_code": "VERIFIER_ERROR:" + type(exc).__name__,
                        "failure_origin": "pipeline", "evidence_refs": refs}
        if function.__name__ in VERIFIERS:
            raise ValueError("Duplicate verifier entry point")
        VERIFIERS[function.__name__] = (identifier, checked)
        return checked
    return bind
