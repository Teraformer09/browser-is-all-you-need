"""Optional API-side action formatting; never repair a model's returned action."""
from copy import deepcopy

def _object(kind, fields=None):
    properties = {"type": {"type": "string", "const": kind}, **(fields or {})}
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}

ACTION_SCHEMA = {"type": "object", "anyOf": [
    _object("tap_element", {"element_id": {"type": "string", "minLength": 1}}),
    _object("type_text", {"element_id": {"type": "string", "minLength": 1},
                          "text": {"type": "string"}}),
    _object("press_back"),
    _object("swipe", {name: {"type": "integer"} for name in
                     ("x1", "y1", "x2", "y2", "duration_ms")}),
    _object("wait"),
    _object("finish"),
]}

def completion_payload(model, messages, response_format="text"):
    payload = {"model": model, "messages": messages, "max_tokens": 2048,
               "temperature": 0, "stream": False}
    if response_format == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "android_ui_action", "strict": True,
                            "schema": deepcopy(ACTION_SCHEMA)},
        }
        # Never silently route to an endpoint that ignores this parameter.
        payload["provider"] = {"require_parameters": True}
    elif response_format == "json_object":
        payload["response_format"] = {"type": "json_object"}
        payload["provider"] = {"require_parameters": True}
    elif response_format != "text":
        raise ValueError("Unknown response format")
    return payload
