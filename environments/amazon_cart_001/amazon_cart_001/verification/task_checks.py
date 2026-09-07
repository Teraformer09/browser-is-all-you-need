"""Full-claim cart policies, not point fragments or button-presence checks."""
import re
from decimal import Decimal
from itertools import product
from amazon_cart_001.verification.contracts import require, Unassessable
from amazon_cart_001.verification.evidence_readers import ui_lines


def endpoint_test(policy, snapshot, task):
    items = task["expected_items"]
    expected = {i["sku"]: i for i in items}
    cart = snapshot["cart_items"]
    rows = {r["sku"]: r for r in cart}
    exact = len(cart) == len(rows) == 3 and set(rows) == set(expected)
    if policy == "T1":
        return exact and all(rows[k]["name"] == expected[k]["name"] for k in expected)
    if policy == "T2":
        return exact and all(type(r["quantity"]) is int and r["quantity"] == 1 for r in cart)
    if policy == "T3":
        return exact and snapshot["currency"] == "INR" and all(
            rows[k]["unit_price_paise"] == expected[k]["unit_price_paise"] for k in expected)
    if policy == "T4":
        sources = [{a["search_id"] for a in snapshot["additions"] if a["sku"] == i["sku"]} for i in items]
        return bool(all(sources) and any(len(set(ids)) == 3 for ids in product(*sources)))
    if policy == "T5":
        return (snapshot["distinct_items"] == len(cart) == 3 and snapshot["total_quantity"] == 3
                and sum(r["quantity"] for r in cart) == 3
                and all(r["line_total_paise"] == r["quantity"] * r["unit_price_paise"] for r in cart)
                and snapshot["subtotal_paise"] == sum(r["line_total_paise"] for r in cart)
                == task["expected_subtotal_paise"])
    if policy == "T6":
        return snapshot["screen"] == "CART" and snapshot["simulated"] is True
    raise Unassessable("UNKNOWN_CART_POLICY")


def cart_complete(snapshot, task):
    return all(endpoint_test(p, snapshot, task) for p in ("T1", "T2", "T3", "T4", "T5", "T6"))


def visual_test(c, policy, frame, method):
    task = c["task"]
    evidence = ui_lines(c, frame, method)
    # A single screen cannot prove a complete search history or arithmetic ledger.
    if policy in {"T3", "T4", "T5"}:
        raise Unassessable("FULL_POLICY_REQUIRES_NONVISUAL_RECORDS")
    if method == "accessibility":
        values = {n["id"]: n["text"] for n in evidence if n["id"]}
        title = values.get("cart_title")
        require(title is not None, "CART_NOT_VISIBLE")
        visible = {k.removeprefix("quantity_") for k in values if k.startswith("quantity_")}
        expected = {i["sku"] for i in task["expected_items"]}
        if policy == "T6":
            return title.startswith("Your cart (") and "cart_subtotal" in values
        # Establish that every cart unit is represented before judging the full set.
        count = re.fullmatch(r"Your cart \((\d+)\)", title)
        quantities = [values["quantity_" + sku] for sku in visible]
        require(count and all(q.isdigit() for q in quantities), "CART_COUNT_UNREADABLE")
        require(int(count[1]) == sum(int(q) for q in quantities), "FULL_CART_NOT_VISIBLE")
        if policy == "T1":
            return visible == expected and all(values.get("title_" + i["sku"]) == i["name"] for i in task["expected_items"])
        return visible == expected and all(values.get("quantity_" + sku) == "1" for sku in expected)
    text = evidence
    if policy == "T6":
        require("Your cart" in text or "Subtotal" in text, "CART_NOT_PIXEL_READABLE")
        return bool(re.search(r"Your cart\s*\(\s*3\s*\)", text) and "Subtotal" in text)
    # No OCR row geometry -> cannot assign a numeric quantity to its product reliably.
    # Nor can cropped pixels establish that no unrequested item exists off-screen.
    raise Unassessable("FULL_PRODUCT_SET_OR_QUANTITY_NOT_PIXEL_PROVEN")
