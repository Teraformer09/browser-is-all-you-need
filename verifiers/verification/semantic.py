"""Task-aware semantic selection checks, separate from action syntax."""
from decimal import Decimal
from amazon_cart_001.harness.actions import permission_error

def semantic_error(a, task):
    if permission_error(a):
        return permission_error(a)
    target = a.get("element_id", "")
    expected = {i["sku"] for i in task["expected_items"]}
    # Queries may vary. Judge product selections, not one prescribed trajectory.
    for prefix in ("add_", "increase_"):
        if target.startswith(prefix) and target.removeprefix(prefix) not in expected:
            return "Unrequested product selection"
    return None
