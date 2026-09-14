"""Distinguish Android input execution from accepted shopping operations."""
def assess_acceptance(action, before, after):
    events = after["state"]["events"][len(before["state"]["events"]):]
    result = {"app_events": events, "accepted": True, "error": None, "failure_origin": "none"}
    rejected = next((e for e in events if e["accepted"] is False), None)
    if rejected:
        return {**result, "accepted": False, "error": rejected["error"], "failure_origin": "agent"}
    target = action.get("element_id", "")
    if action["type"] == "type_text":
        confirmed = after["state"].get("draft_query") == action["text"]
    elif action["type"] == "tap_element" and target == "search_input":
        confirmed = any(n["id"] == target and n.get("focused") is True for n in after.get("ui", []))
    elif action["type"] == "tap_element":
        event = {"search_button": "search", "cart_button": "open_cart",
                 "continue_shopping_button": "continue_shopping"}.get(target)
        for prefix, kind in (("add_", "add_to_cart"), ("increase_", "increase_quantity"),
                             ("decrease_", "decrease_quantity"), ("remove_", "remove_item")):
            if target.startswith(prefix):
                event = kind
        confirmed = event is not None and any(e["action"] == event for e in events)
    else:
        confirmed = True
    if not confirmed:
        return {**result, "accepted": None, "error": "Requested UI effect lacks an app receipt",
                "failure_origin": "pipeline"}
    return {**result, "acceptance_evidence": "observed_input_or_app_event"}
