"""Read-only evidence primitives shared by dedicated policy verifiers."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from uber_clone_031.verification.records import parse_state

class Unassessable(ValueError):
    pass


def frames(context):
    values = context.get("frames")
    if not isinstance(values, list) or not values:
        raise Unassessable("NO_EPISODE_FRAMES")
    if [f.get("index") for f in values] != list(range(len(values))):
        raise Unassessable("FRAME_SEQUENCE_GAP")
    return values


def action_pairs(context):
    values = frames(context)
    return [(values[i-1], frame) for i, frame in enumerate(values)
            if i and frame.get("is_action", frame.get("info") is not None)]


def raw_action(frame):
    value = frame.get("action")
    if isinstance(value, str):
        value = value.strip()
        if value.startswith("```"):
            value = "\n".join(value.splitlines()[1:-1]).strip()
        try: return json.loads(value)
        except json.JSONDecodeError: return value
    return value


def action_type(value):
    if not isinstance(value, dict): return None
    kind = value.get("type", value.get("action"))
    if not isinstance(kind, str): return None
    return {"click_resource": "tap_element", "input_resource": "type_text"}.get(kind, kind)


def target_id(value):
    if not isinstance(value, dict): return None
    value = value.get("element_id", value.get("target"))
    return value.rsplit("/", 1)[-1] if isinstance(value, str) else None


def prefs(frame, context):
    value = parse_state(frame.get("observation", {}).get("prefs_xml", ""))
    if not value or value.get("episode_id") != context["episode_id"]:
        raise Unassessable("PREFERENCES_MISSING_MALFORMED_OR_STALE")
    return value


def runtime(frame, context):
    value = frame.get("runtime_probe")
    if not isinstance(value, dict) or value.get("episode_id") != context["episode_id"]:
        raise Unassessable("RUNTIME_PROBE_MISSING_OR_STALE")
    if value.get("contract_version") != context["registry"]["app"]["contract_version"]:
        raise Unassessable("RUNTIME_CONTRACT_MISMATCH")
    return value


def replay(frame, context):
    events = frame.get("mutations")
    if not isinstance(events, list) or not events:
        raise Unassessable("MUTATION_LOG_UNAVAILABLE")
    if not events[0].get("initial") or events[0].get("seq") != 0 or events[0].get("before") is not None:
        raise Unassessable("MUTATION_LOG_NO_INITIAL_STATE")
    previous = None
    for index, event in enumerate(events):
        state = event.get("state")
        if event.get("seq") != index or event.get("episode_id") != context["episode_id"] or not isinstance(state, dict):
            raise Unassessable("MUTATION_SEQUENCE_OR_EPISODE_GAP")
        if state.get("episode_id") != context["episode_id"] or str(state.get("ride_action_sequence")) != str(index):
            raise Unassessable("MUTATION_STATE_IDENTITY_MISMATCH")
        if index and event.get("before") != previous:
            raise Unassessable("MUTATION_CHAIN_DISCONTINUITY")
        previous = state
    expected = frame.get("app_sequence")
    if expected is None or str(events[-1]["seq"]) != str(expected):
        raise Unassessable("MUTATION_LOG_TRUNCATED")
    return previous


def artifact_bytes(context, artifact):
    if not isinstance(artifact, dict) or not artifact.get("path") or not artifact.get("sha256"):
        raise Unassessable("ARTIFACT_REFERENCE_MISSING")
    root = Path(context["run_dir"]).resolve()
    path = (root / artifact["path"]).resolve()
    if not path.is_relative_to(root):
        raise Unassessable("ARTIFACT_PATH_OUTSIDE_RUN")
    try: data = path.read_bytes()
    except OSError as exc: raise Unassessable("ARTIFACT_UNREADABLE") from exc
    if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
        raise Unassessable("ARTIFACT_HASH_MISMATCH")
    return data


def ui_root(frame, context):
    if frame.get("observation", {}).get("observation_freshness", {}).get("fresh") is not True:
        raise Unassessable("UI_NOT_FRESH")
    # UI has no episode ID itself; bind it to its synchronized app snapshot.
    prefs(frame, context)
    try: root = ET.fromstring(frame.get("observation", {}).get("ui_tree_xml", ""))
    except ET.ParseError as exc: raise Unassessable("UI_UNREADABLE") from exc
    if root.tag != "hierarchy": raise Unassessable("UI_NOT_HIERARCHY")
    return root


def summary_state(text):
    compact = " ".join(text.split())
    # The progress node repeats Pickup as a set/unset diagnostic, not a route.
    # Keep its stage, excluding only this exact clause from ambiguity checks.
    # OCR may omit the bullet; other repeated labels remain ambiguous.
    compact = re.sub(
        r"\b(Booking step\s+[0-5]/5)\s*(?:[•·]\s*)?Pickup:\s*(?:not\s+set|set)\b",
        r"\1", compact, flags=re.IGNORECASE,
    )
    if any(compact.casefold().count(label) != 1 for label in ("pickup:", "ride:", "destination:", "cab:", "payment:")):
        raise Unassessable("SUMMARY_DUPLICATED_OR_AMBIGUOUS")
    pattern = r"Pickup:\s*(.*?)\s*\|\s*Ride:\s*(.*?)\s*\|\s*Destination:\s*(.*?)\s*\|\s*Cab:\s*(.*?)\s*\|\s*Payment:\s*(card|cash|upi|not set)\b"
    match = re.search(pattern, compact, re.IGNORECASE)
    if not match: raise Unassessable("SUMMARY_MISSING_AMBIGUOUS_OR_OFFSCREEN")
    state = dict(zip(("ride_pickup", "ride_type", "ride_drop", "selected_ride", "payment"), match.groups()))
    for key, value in state.items():
        state[key] = "" if value.strip().lower() == "not set" else value.strip()
    stage = re.search(r"Booking step\s+(\d)/5", compact)
    if stage: state["journey_stage"] = stage.group(1)
    # Selection buttons alone do not establish these terminal facts.
    if re.search(r"Ride booked:", compact, re.IGNORECASE):
        state.update(screen="ride_booked", ride_confirmed="true", ride_cancelled="false")
    elif re.search(r"Ride cancelled\.", compact, re.IGNORECASE):
        state.update(screen="ride_cancelled", ride_confirmed="false", ride_cancelled="true")
    return state


def accessibility(frame, context):
    root = ui_root(frame, context)
    names = ("route_summary_text", "ride_progress_text", "final_status_text")
    texts = [node.get("text", "") for node in root.iter("node")
             if node.get("resource-id", "").rsplit("/", 1)[-1] in names]
    return summary_state(" ".join(texts))


def screenshot(frame, context):
    artifact_bytes(context, frame.get("screenshot"))
    ocr = frame.get("ocr")
    if not isinstance(ocr, dict) or ocr.get("source_sha256") != frame["screenshot"]["sha256"] or ocr.get("error"):
        raise Unassessable("SCREENSHOT_OCR_UNAVAILABLE")
    prefs(frame, context)
    if not ocr.get("text"): raise Unassessable("SCREENSHOT_OCR_EMPTY")
    if ocr.get("min_confidence", 0) < context["registry"]["ui"].get("ocr_min_confidence", 90):
        raise Unassessable("SCREENSHOT_OCR_UNCERTAIN")
    return summary_state(ocr["text"])


SOURCES = (prefs, accessibility, screenshot, replay, runtime)
FIELD_BINDINGS = {"T1": ("ride_pickup", "pickup"), "T2": ("ride_type", "ride_type"),
                  "T3": ("ride_drop", "destination"), "T4": ("selected_ride", "cab_type"),
                  "T5": ("payment", "payment_method")}


def field_check(context, policy, source_index):
    frame = frames(context)[-1]
    state = SOURCES[source_index](frame, context)
    interrupted = context.get("failure_origin") == "pipeline" and state.get("ride_confirmed") != "true"
    if policy == "T6":
        expected = context["registry"]["topic"]["predicates"]["correct_booking_committed"]
        missing = [key for key in expected if key not in state]
        mismatches = [key for key, value in expected.items() if key in state and str(state[key]) != value]
        if mismatches:
            if interrupted: raise Unassessable("PIPELINE_INTERRUPTED_BEFORE_BOOKING_ASSESSMENT")
            return False, "BOOKING_NOT_COMPLETE", state, expected
        if missing: raise Unassessable("TERMINAL_BOOKING_FACTS_UNAVAILABLE")
        return True, "BOOKING_COMMITTED", state, expected
    field, parameter = FIELD_BINDINGS[policy]
    if field not in state: raise Unassessable("REQUIRED_FIELD_UNREADABLE")
    actual, expected = str(state[field]), context["registry"]["task"]["expected"][parameter]
    # UI/OCR capitalization is not a different location or payment identity.
    equal = actual.casefold() == expected.casefold() if source_index in {1, 2} else actual == expected
    if not equal and interrupted:
        raise Unassessable("PIPELINE_INTERRUPTED_BEFORE_VALUE_ASSESSMENT")
    return equal, "VALUE_MATCH" if equal else "VALUE_WRONG_OR_UNSET", actual, expected
