from payment_transfer_001.verification.generic.validity import validity_check
from payment_transfer_001.verification.semantic import semantic_error
from payment_transfer_001.verification.contracts import Unassessable, require
from payment_transfer_001.verification.evidence_readers import artifact, state
from payment_transfer_001.verification.task_checks import endpoint_test
import copy
import json
import re
import xml.etree.ElementTree as ET
from payment_transfer_001.harness.actions import PACKAGE, decode, schema_error, permission_error
from payment_transfer_001.harness.evidence import nodes
from payment_transfer_001.verification.records import verify as record_verify


def target_ok(action, frame):
    if action.get("type") not in {"tap_element", "type_text"}:
        return True
    target = next((n for n in frame.get("ui", []) if n["id"] == action["element_id"]), None)
    if not target:
        return False
    l,t,r,b = target["bounds"]
    return target["enabled"] and r>l and b>t and (target["clickable"] or target["class"].endswith("EditText"))


def generic_check(c, policy, method):
    frames, transitions = c["frames"], c["transitions"]
    require(frames, "NO_EPISODE_FRAMES")
    for transition in transitions:
        require(decode(transition["raw_response"]) == transition["action"] == transition["receipt"]["requested_action"],
                "ACTION_TRACE_BINDING_MISMATCH")
    # Select the concrete evidence path before checking the full claim.
    if method == "model_trace":
        source = [decode(t["raw_response"]) for t in transitions]
    elif method == "action_records":
        source = [t["action"] for t in transitions]
    elif method == "dispatch_receipts":
        source = [t["receipt"]["requested_action"] for t in transitions]
    elif method == "adb_trace":
        require(isinstance(c.get("adb_trace"), list), "ADB_TRACE_MISSING")
        source = [t["action"] for t in transitions]
        for t in transitions:
            require(type(t["trace_start"]) is int and type(t["trace_end"]) is int, "ADB_SPAN_MISSING")
    else:
        source = [t["action"] for t in transitions]
        for frame in frames:
            state(c, frame, "journal_replay")
    if policy in {"V1", "V2"}:
        return validity_check(c, policy)
    if c.get("pipeline_error") and not transitions:
        raise Unassessable("NO_ASSESSABLE_ACTIONS")
    for i, (action, transition) in enumerate(zip(source, transitions)):
        before, after, receipt = frames[i], frames[i+1], transition["receipt"]
        require(action == decode(transition["raw_response"]), "ACTION_NOT_BOUND_TO_MODEL_OUTPUT")
        if policy == "G1" and schema_error(action):
            return False
        if policy == "G2" and permission_error(action):
            return False
        if policy == "G3":
            if schema_error(action):
                return False
            require(before.get("stable") and not before.get("errors"), "TARGET_EVIDENCE_UNAVAILABLE")
            visual_before = dict(before, ui=nodes(artifact(c, before, "ui.xml", "text")))
            if not target_ok(action, visual_before):
                return False
        if policy == "G4":
            require(receipt["failure_origin"] != "pipeline", "TRANSPORT_FAILURE")
            if not receipt["executed"]:
                return False
            span = c["adb_trace"][transition["trace_start"]:transition["trace_end"]]
            if action["type"] not in {"wait","finish"}:
                require(span, "MISSING_ACTION_COMMAND_RECEIPTS")
                require(all(r.get("returncode") == 0 and not r.get("error") for r in span), "ADB_EXECUTION_UNPROVEN")
        if policy == "S1" and semantic_error(action, c["task"]["expected"]):
            return False
        if policy == "T7":
            require(receipt["failure_origin"] != "pipeline", "ACTION_CONTRACT_UNASSESSABLE")
            if schema_error(action) or permission_error(action) or not receipt["executed"] or receipt["accepted"] is False:
                return False
            current = state(c, after, "journal_replay")
            if any(e["accepted"] is False for e in after["state"]["events"]):
                return False
            if action["type"] == "finish" and not endpoint_test("T6", current, c["task"]["expected"]):
                return False
            if len(current["transactions"]) > 1:
                return False
    return len(transitions) <= c["task"]["max_steps"] if policy == "T7" else True
