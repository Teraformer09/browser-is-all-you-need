"""Separate focus, text replacement, and business-state acceptance."""
INPUT_FIELDS = {"amount_input":"amount_input","note_input":"note"}
APP_EVENTS = {"recipient_alex":"select_recipient","recipient_blair":"select_recipient",
    "account_1234":"select_account","account_5678":"select_account",
    "amount_input":"enter_amount","note_input":"enter_note",
    "review_button":"review","confirm_transfer_button":"confirm"}

def assess_acceptance(action,before,after):
    events=after["state"]["events"][len(before["state"]["events"]):]
    result={"app_events":events,"accepted":True,"error":None,"failure_origin":"none"}
    rejected=next((event for event in events if event["accepted"] is False),None)
    if rejected is not None:
        return {**result,"accepted":False,"error":rejected["error"],"failure_origin":"agent"}
    target=action.get("element_id")
    if action["type"]=="tap_element" and target in INPUT_FIELDS:
        node=next((n for n in after.get("ui",[]) if n["id"]==target),None)
        if node and node.get("focused") is True:
            return {**result,"acceptance_evidence":"post_action_ui_focus"}
        return {**result,"accepted":None,"error":"Input focus could not be established","failure_origin":"pipeline"}
    if action["type"]=="type_text":
        field=INPUT_FIELDS[target]
        if after["state"].get(field)==action["text"]:
            return {**result,"acceptance_evidence":"post_action_input_value"}
        return {**result,"accepted":None,"error":"Text replacement effect could not be established","failure_origin":"pipeline"}
    if action["type"]=="tap_element" and not any(e["action"]==APP_EVENTS[target] for e in events):
        return {**result,"accepted":None,"error":"Missing business-action event receipt","failure_origin":"pipeline"}
    return {**result,"acceptance_evidence":"app_event" if events else "non_mutating_action"}
