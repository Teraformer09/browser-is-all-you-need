"""Explicit smoke-test reference actions, never a model fallback or hidden repair."""
def actions(task):
    expected = task["expected"]
    paise = expected["amount_paise"]
    return [
        {"type":"tap_element", "element_id":"recipient_" + expected["recipient_id"]},
        {"type":"type_text", "element_id":"amount_input", "text":f"{paise // 100}.{paise % 100:02d}"},
        {"type":"tap_element", "element_id":expected["account_id"]},
        {"type":"type_text", "element_id":"note_input", "text":expected["note"]},
        {"type":"press_back"},
        {"type":"tap_element", "element_id":"review_button"},
        {"type":"tap_element", "element_id":"confirm_transfer_button"},
    ]
