"""Task-aware semantic selection checks, separate from action syntax."""
from decimal import Decimal
from payment_transfer_001.harness.actions import permission_error

def semantic_error(a, expected):
    if permission_error(a):
        return permission_error(a)
    target = a.get("element_id", "")
    if target.startswith("recipient_") and target.removeprefix("recipient_") != expected["recipient_id"]:
        return "Wrong recipient selection"
    if target.startswith("account_") and target != expected["account_id"]:
        return "Wrong account selection"
    if a["type"] == "type_text" and target == "amount_input":
        try:
            if Decimal(a["text"]) * 100 != expected["amount_paise"]:
                return "Wrong amount entry"
        except Exception:
            return "Uninterpretable amount entry"
    if a["type"] == "type_text" and target == "note_input" and a["text"] != expected["note"]:
        return "Wrong note entry"
    return None
