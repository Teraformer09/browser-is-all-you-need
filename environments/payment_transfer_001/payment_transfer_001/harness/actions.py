"""Strict JSON action contract; no action repair, shell tools, or oracle fallback."""
import json
import re
from decimal import Decimal

PACKAGE = "com.primeintellect.paymentdemo"
TARGETS = {"recipient_alex", "recipient_blair", "account_1234", "account_5678",
           "amount_input", "note_input", "review_button", "confirm_transfer_button"}
INPUTS = {"amount_input", "note_input"}
KINDS = {"tap_element", "type_text", "press_back", "swipe", "wait", "finish"}
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["type"],
    "properties": {"type": {"enum": sorted(KINDS)},
        "element_id": {"type": "string"}, "text": {"type": "string"},
        **{k: {"type": "integer"} for k in ("x1", "y1", "x2", "y2", "duration_ms")}},
}

def decode(content):
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None

def schema_error(a):
    if not isinstance(a, dict) or not isinstance(a.get("type"), str):
        return "Expected exactly one JSON action object"
    kind = a["type"]
    if kind not in KINDS:
        return "Unsupported action type"
    fields = {"type"}
    if kind in {"tap_element", "type_text"}:
        fields.add("element_id")
        if not isinstance(a.get("element_id"), str) or not a["element_id"]:
            return "Missing string element_id"
    if kind == "type_text":
        fields.add("text")
        if not isinstance(a.get("text"), str) or len(a["text"]) > 80:
            return "Text must be a string of at most 80 characters"
    if kind == "swipe":
        fields.update(("x1", "y1", "x2", "y2", "duration_ms"))
        if any(type(a.get(k)) is not int for k in fields - {"type"}):
            return "Swipe requires integer coordinates and duration_ms"
        if not 100 <= a["duration_ms"] <= 1000:
            return "Swipe duration must be 100..1000 ms"
    return None if set(a) == fields else "Unexpected or missing action fields"

def permission_error(a):
    if schema_error(a):
        return "Malformed action is not permitted"
    target = a.get("element_id")
    if target is not None and target not in TARGETS:
        return "Target is not in this app's permitted controls"
    if a["type"] == "type_text":
        if target not in INPUTS:
            return "Target is not an input"
        if not re.fullmatch(r"[A-Za-z0-9 ._-]*", a["text"]):
            return "Only plain ASCII letters, digits, spaces, dot, underscore and hyphen are supported"
    return None
