"""Read frozen evidence and replay accepted operations; never mutate Android."""
import copy
import json
from pathlib import Path
from amazon_cart_001.harness.evidence import digest, nodes, prefs_snapshot
from amazon_cart_001.verification.contracts import require, Unassessable
from amazon_cart_001.verification.records import verify


def artifact(c, frame, name, mode="json"):
    require(frame.get("episode_id") == c["episode_id"], "FRAME_EPISODE_MISMATCH")
    ref = frame.get("artifacts", {}).get(name)
    require(isinstance(ref, dict), "EVIDENCE_MISSING:" + name)
    root = Path(c["root"]).resolve()
    path = (root / ref["path"]).resolve()
    require(path.is_relative_to(root), "EVIDENCE_PATH_ESCAPE")
    data = path.read_bytes()
    require(digest(data) == ref["sha256"], "EVIDENCE_HASH_MISMATCH:" + name)
    return json.loads(data) if mode == "json" else data.decode() if mode == "text" else data


def catalog():
    spec = Path(__file__).parents[1] / "specs/app_contract.json"
    return json.loads(spec.read_text())["catalog"]


def replay_operations(operations, episode):
    """Reconstruct every business field from operations, not cached event state."""
    products = {p["sku"]: p for p in catalog()}
    cart, searches, additions = {}, [], []
    draft = query = ""
    screen, revision = "BROWSE", 0

    def search(text):
        tokens = text.strip().lower().split()
        if len(" ".join(tokens)) < 2:
            return []
        return [sku for sku, p in products.items()
                if all(t in (p["name"] + " " + p["detail"] + " " + p["category"]).lower() for t in tokens)]

    require(isinstance(operations, list), "OPERATIONS_MISSING")
    for op in operations:
        kind = op["type"]
        fields = {"draft": {"type", "text"}, "search": {"type", "query"},
                  "add": {"type", "sku"}, "cart": {"type"}, "browse": {"type"},
                  "adjust": {"type", "sku", "delta"}, "remove": {"type", "sku"}}
        require(kind in fields and set(op) == fields[kind], "OPERATION_SCHEMA_INVALID")
        if kind == "draft":
            value = op["text"]
            require(isinstance(value, str) and len(value) <= 80 and value != draft, "DRAFT_REPLAY_INVALID")
            draft = value
        elif kind == "search":
            require(screen == "BROWSE" and op["query"] == draft and len(draft.strip()) >= 2, "SEARCH_REPLAY_INVALID")
            query = draft
            searches.append({"search_id": len(searches) + 1, "query": query, "result_skus": search(query)})
        elif kind == "add":
            sku = op["sku"]
            require(screen == "BROWSE" and searches and draft == query and sku in search(query)
                    and cart.get(sku, 0) < 9, "ADD_REPLAY_INVALID")
            cart[sku] = cart.get(sku, 0) + 1
            additions.append({"sku": sku, "search_id": len(searches), "query": query, "quantity_after": cart[sku]})
        elif kind in {"cart", "browse"}:
            screen = "CART" if kind == "cart" else "BROWSE"
        else:
            sku = op["sku"]
            require(screen == "CART" and sku in cart, "CART_MUTATION_REPLAY_INVALID")
            if kind == "remove":
                del cart[sku]
            else:
                delta = op["delta"]
                require(type(delta) is int and delta in {-1, 1} and 0 <= cart[sku] + delta <= 9,
                        "QUANTITY_REPLAY_INVALID")
                cart[sku] += delta
                if not cart[sku]:
                    del cart[sku]
        revision += 1
    rows = [{**products[sku], "quantity": qty, "line_total_paise": products[sku]["unit_price_paise"] * qty}
            for sku, qty in cart.items()]
    current = bool(searches) and draft == query
    return {"schema_version": 1, "episode_id": episode, "simulated": True, "currency": "INR", "screen": screen,
            "draft_query": draft, "query": query, "results_current": current,
            "result_skus": search(query) if current else [], "searches": searches, "additions": additions,
            "operations": copy.deepcopy(operations), "cart_items": rows, "distinct_items": len(cart),
            "total_quantity": sum(cart.values()), "subtotal_paise": sum(r["line_total_paise"] for r in rows),
            "revision": revision}


def state(c, frame, method):
    require(frame.get("stable") is True and not frame.get("errors"), "FRAME_NOT_STABLE")
    if method == "persisted_state":
        value = prefs_snapshot(artifact(c, frame, "preferences.xml", "text"))
    elif method == "runtime_probe":
        value = artifact(c, frame, "runtime.json")
    elif method == "journal_replay":
        events = artifact(c, frame, "journal.json")
        require(isinstance(events, list) and events and events[0]["action"] == "open"
                and events[0]["state"].get("operations") == [], "JOURNAL_INITIALIZATION_MISSING")
        previous = []
        for i, event in enumerate(events):
            require(type(event["sequence"]) is int and event["sequence"] == i
                    and type(event["accepted"]) is bool, "JOURNAL_GAP")
            snapshot = event["state"]
            operations = snapshot["operations"]
            require(operations[:len(previous)] == previous, "OPERATION_HISTORY_REWRITTEN")
            require(event["accepted"] or operations == previous, "REJECTED_ACTION_MUTATED_STATE")
            replayed = replay_operations(operations, c["episode_id"])
            require(replayed == snapshot, "EVENT_STATE_REPLAY_MISMATCH")
            previous = operations
        value = replayed
    else:
        raise Unassessable("UNKNOWN_STATE_CHANNEL")
    require(verify(value, c["task"], c["episode_id"])["status"] != "INVALID", "STATE_SCHEMA_OR_EPISODE_INVALID")
    return value


def ui_lines(c, frame, method):
    require(frame.get("stable") is True and not frame.get("errors"), "VISUAL_FRAME_NOT_ATTRIBUTABLE")
    if method == "accessibility":
        return nodes(artifact(c, frame, "ui.xml", "text"))
    ocr = artifact(c, frame, "ocr.json")
    require(ocr["source_sha256"] == digest(artifact(c, frame, "screen.png", "bytes")), "OCR_IMAGE_MISMATCH")
    words = [w["text"] for w in ocr["words"] if float(w.get("conf", -1)) >= 70]
    return " ".join(words)
