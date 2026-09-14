"""Nine action-correctness checks plus five shared, measured episode budgets.

No verifier changes app state. Controller receipts are not actor-supplied tools.
Legacy weighted task votes are replaced, not added to the new episode reward.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from amazon_improved_task_001.harness.actions import schema_error
from amazon_improved_task_001.verification import strict
from amazon_improved_task_001.verification.contracts import require, Unassessable
from amazon_improved_task_001.verification.peach import endpoint, progress, task_spec

SPEC = Path(__file__).resolve().parents[1] / "specs/action_budget.json"
PROFILE = "peach_action_budget_v1"
REWARDS = {"PASS": 1, "INVALID": 0, "FAIL": -1}
CORRECTNESS = ("query_entry", "search_submission", "cart_addition")
BUDGETS = (("O1", "text_entries", 3), ("O2", "taps", 7), ("O3", "total_actions", 11),
           ("O4", "completion_tokens", 165), ("O5", "model_request_seconds", 13))
GATES = ("contract", "evidence_integrity", "timeline", "action_audit", "cart_lineage", "exact_outcome")


def identity():
    package = SPEC.parent.parent
    files = ["verification/action_budget.py", "specs/action_budget.json", "specs/peach_task.json"]
    hashes = strict.rubric_identity()["source_hashes"] | {
        f: hashlib.sha256((package / f).read_bytes()).hexdigest() for f in files}
    return {"id": PROFILE, "version": "0.1.0", "source_hashes": hashes,
            "sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def result(check_id, status, reason, *, actual=None, expected=None, refs=()):
    return {"check_id": check_id, "status": status, "reward": REWARDS[status],
            "reason_code": reason, "actual": actual, "expected": expected, "evidence_refs": list(refs)}


def aggregate(rows):
    statuses = [r["status"] for r in rows]
    return "FAIL" if "FAIL" in statuses else "INVALID" if not rows or "INVALID" in statuses else "PASS"


def specification():
    spec = json.loads(SPEC.read_text())
    require(spec["rubric_id"] == PROFILE and spec["policy_cutoff_tenths"] == 9 and
            spec["correctness_checks"] == list(CORRECTNESS) and
            [(b["id"], b["metric"], b["maximum"]) for b in spec["optimizers"]] == list(BUDGETS) and
            spec["status_to_reward"] == REWARDS, "SCORING_SPEC_MISMATCH")
    return spec


def events(before, after):
    old, new = before["tables"]["eval_events"], after["tables"]["eval_events"]
    require(new[:len(old)] == old, "JOURNAL_REWRITTEN")
    return [(e["sequence"], e["kind"], json.loads(e["payload"])) for e in new[len(old):]]


def candidates(c, frames, item):
    """Find actual text->search->add chains; permit different matching query text.

    A subsequent mutation that removes the item invalidates that acquisition.
    A new acquisition must establish a fresh, correctly bound chain of its own.
    """
    entry, search, acquisitions = None, None, []
    sku = item["sku"]
    for i, transition in enumerate(c["transitions"]):
        a, receipt = transition["action"], transition["receipt"]
        before, after = frames[i], frames[i + 1]
        if schema_error(a) or receipt.get("accepted") is not True or receipt.get("executed") is not True:
            continue
        new = events(before, after)
        if a["type"] == "type_text" and a["element_id"] == "search_input":
            entry = (i + 1, a["text"]) if after["state"]["draft"] == a["text"] else None
            search = None
        if a == {"type": "tap_element", "element_id": "search_button"}:
            search = None
            searches = [(seq, data) for seq, kind, data in new if kind == "search"]
            if entry and len(searches) == 1:
                seq, data = searches[0]
                matches = next((s for s in after["state"]["searches"] if s["search_id"] == seq), None)
                if (data["query"] == entry[1].strip() == before["state"]["draft"].strip() and
                        after["state"]["page"] == "results" and matches and sku in matches["result_skus"]):
                    search = {"entry_step": entry[0], "query": entry[1], "search_step": i + 1, "search_id": seq}
        mutations = [(kind, data) for _, kind, data in new if kind in {"add", "decrease", "remove"}]
        products = {p["id"]: p["sku"] for p in after["tables"]["products"]}
        for kind, data in mutations:
            if products[data["product_id"]] != sku:
                continue
            previous = next((r["quantity"] for r in before["state"]["cart"] if r["sku"] == sku), 0)
            if data["quantity_after"] == 0:
                acquisitions = []
            if kind == "add" and previous == 0:
                acquisitions = []
                if (search and a.get("element_id") in {"add_" + sku, "increase_" + sku} and
                        data["quantity_after"] == item["quantity"] and before["state"]["query"] == search["query"].strip()):
                    acquisitions.append({**search, "add_step": i + 1})
    return entry, search, acquisitions


def verify_query_entry(c, frames, item, chain):
    matches = []
    for i, transition in enumerate(c["transitions"]):
        a, r = transition["action"], transition["receipt"]
        if schema_error(a) or a["type"] != "type_text" or a.get("element_id") != "search_input":
            continue
        product = next(p for p in frames[i + 1]["tables"]["products"] if p["sku"] == item["sku"])
        text = (product["name"] + " " + product["category"] + " " + product["sku"]).casefold()
        query = a["text"].strip()
        if (query and all(word in text for word in query.casefold().split()) and r.get("accepted") is True and
                r.get("executed") is True and frames[i + 1]["state"]["draft"] == a["text"]):
            matches.append(i + 1)
    chosen = chain.get("entry_step") if chain else (matches[-1] if matches else None)
    return bool(chosen in matches), chosen


def verify_search_submission(c, frames, item, chain):
    matches = []
    for i, transition in enumerate(c["transitions"]):
        if transition["action"] != {"type": "tap_element", "element_id": "search_button"}:
            continue
        r = transition["receipt"]
        if not (r.get("accepted") is True and r.get("executed") is True):
            continue
        for seq, kind, data in events(frames[i], frames[i + 1]):
            if kind != "search" or data["query"] != frames[i]["state"]["draft"].strip():
                continue
            hit = next((s for s in frames[i + 1]["state"]["searches"] if s["search_id"] == seq), None)
            if hit and item["sku"] in hit["result_skus"] and frames[i + 1]["state"]["page"] == "results":
                matches.append(i + 1)
    chosen = chain.get("search_step") if chain else (matches[-1] if matches else None)
    return bool(chosen in matches), chosen


def verify_cart_addition(c, frames, item, chain):
    final = next((r for r in frames[-1]["state"]["cart"] if r["sku"] == item["sku"]), None)
    correct = bool(final and all(final.get(key) == item[key] for key in ("name", "quantity", "unit_price_paise")))
    return bool(chain and correct), chain.get("add_step") if chain else None


CHECKS = {"query_entry": verify_query_entry, "search_submission": verify_search_submission,
          "cart_addition": verify_cart_addition}


def correctness(c, frames, item):
    rows = []
    try:
        _, _, chains = candidates(c, frames, item)
        chain = chains[-1] if chains else None
    except strict.ERRORS as exc:
        return [result(item["sku"] + "." + name, "INVALID", str(exc)) for name in CORRECTNESS]
    for name in CORRECTNESS:
        try:
            passed, step = CHECKS[name](c, frames, item, chain)
            refs = ["trajectory.jsonl", f"frames/{len(frames)-1:03d}/database.sqlite"]
            if step:
                refs += [f"frames/{step:03d}/screen.png", f"frames/{step:03d}/ui.xml",
                         f"frames/{step:03d}/database.sqlite"]
            rows.append(result(item["sku"] + "." + name, "PASS" if passed else "FAIL",
                               "ACTION_STATE_CONFIRMED" if passed else "REQUIRED_ACTION_UNMET",
                               actual={"step": step, "chain": chain}, expected=item, refs=refs))
        except strict.ERRORS as exc:
            rows.append(result(item["sku"] + "." + name, "INVALID", str(exc)))
    return rows


def model_metrics(c):
    envelope = c.get("model_evidence")
    require(isinstance(envelope, dict) and envelope.get("schema_version") == 1 and
            envelope.get("episode_id") == c["episode_id"] and envelope.get("source") == "host_controller",
            "MODEL_EVIDENCE_MISSING_OR_WRONG_EPISODE")
    requests = envelope.get("requests")
    require(isinstance(requests, list) and 0 < len(requests) <= 72, "MODEL_RECEIPTS_MISSING")
    bound = []
    for index, r in enumerate(requests):
        require(isinstance(r, dict) and r.get("request_index") == index + 1, "MODEL_RECEIPT_SEQUENCE")
        step = r.get("action_step")
        if step is not None:
            require(type(step) is int and 1 <= step <= len(c["transitions"]), "MODEL_ACTION_BINDING")
            require(r.get("raw_response") == c["transitions"][step - 1]["raw_response"], "MODEL_RESPONSE_BINDING")
            bound.append(step)
    require(bound == list(range(1, len(c["transitions"]) + 1)), "MODEL_ACTION_COVERAGE")
    values, errors = {}, {}
    for key, receipt_key, integral in (("completion_tokens", "completion_tokens", True),
                                      ("model_request_seconds", "elapsed_seconds", False)):
        numbers = [r.get(receipt_key) for r in requests]
        valid = all(type(v) is int if integral else type(v) in (int, float) for v in numbers)
        if not valid or not all(math.isfinite(v) and v >= 0 for v in numbers):
            errors[key] = "MISSING_OR_INVALID_" + receipt_key.upper()
        else:
            values[key] = sum(numbers)
    return values, errors


def optimizer_results(c, trusted_actions):
    metrics, errors = {}, {}
    if trusted_actions:
        actions = [t["action"] for t in c["transitions"]]
        metrics.update(text_entries=sum(a.get("type") == "type_text" for a in actions if isinstance(a, dict)),
                       taps=sum(a.get("type") == "tap_element" for a in actions if isinstance(a, dict)),
                       total_actions=len(actions))
    try:
        measured, failures = model_metrics(c)
        metrics.update(measured)
        errors.update(failures)
    except strict.ERRORS as exc:
        errors.update(completion_tokens=str(exc), model_request_seconds=str(exc))
    results = []
    for check_id, metric, maximum in BUDGETS:
        value = metrics.get(metric)
        status = "INVALID" if value is None else "PASS" if value <= maximum else "FAIL"
        results.append(result(check_id, status, errors.get(metric, "METRIC_UNAVAILABLE") if value is None else
                              "WITHIN_CAP" if status == "PASS" else "CAP_EXCEEDED", actual=value,
                              expected={"metric": metric, "comparison": "<=", "maximum": maximum},
                              refs=["trajectory.jsonl"] if check_id in {"O1", "O2", "O3"} else ["model_evidence.json"]))
    return results


def score_policy(policy_id, checks, optimizers, terminal=True):
    require(len(checks) == 3 and len({c["check_id"] for c in checks}) == 3 and
            len(optimizers) == 5 and [r["check_id"] for r in optimizers] == [b[0] for b in BUDGETS],
            "INCOMPLETE_POLICY_RESULTS")
    baseline = aggregate(checks)
    passed = sum(r["status"] == "PASS" for r in optimizers)
    tenths = 5 + passed if baseline == "PASS" else 0
    status = (baseline if baseline != "PASS" else "INVALID" if all(r["status"] == "INVALID" for r in optimizers)
              else "PASS" if tenths >= 9 else "FAIL")
    return {"policy_id": policy_id, "baseline_status": baseline, "baseline_reward": 0.5 if baseline == "PASS" else 0,
            "correctness_results": checks, "optimizer_refs": ["shared_optimizers/" + r["check_id"] for r in optimizers],
            "passed_optimizers": passed, "support_score": tenths / 10, "cutoff": 0.9,
            "status": status if terminal else "PENDING", "reward": REWARDS[status] if terminal else None,
            "pass_condition": "Three correctness checks PASS and at least four of five shared budget checks PASS.",
            "fail_condition": "Assessable baseline failure, or fewer than four budget PASS results (unless all five INVALID).",
            "invalid_condition": "Essential baseline evidence unavailable, or all five budget results INVALID."}


def evaluate(c):
    terminal = c.get("actor_stopped") is True
    gates, frames = [], None
    try:
        specification()
        strict.contract(c)
        gates.append(result("contract", "PASS", "SPEC_AND_APK_CONFIRMED", refs=["installed_apk.json"]))
        frames = strict.frozen_frames(c)
        gates.append(result("evidence_integrity", "PASS", "FROZEN_FILES_CONFIRMED", refs=["frames/*"]))
        for name, predicate in (
                ("timeline", lambda: strict.timeline(c, frames)),
                ("action_audit", lambda: strict.action_audit(c, frames)),
                ("cart_lineage", lambda: strict.cart_lineage(frames[-1]["tables"], c["task"])),
                ("exact_outcome", lambda: all(endpoint(p, frames[-1]["state"], c["task"])
                                             for p in ("T1", "T2", "T3", "T4", "T5", "T6")))):
            try:
                ok = predicate()
                gates.append(result(name, "PASS" if ok else "FAIL", "CONFIRMED" if ok else "REQUIRED_CLAIM_UNMET",
                                    refs=["context.json", "trajectory.jsonl", "frames/*"]))
            except strict.ERRORS as exc:
                gates.append(result(name, "INVALID", str(exc)))
    except strict.ERRORS as exc:
        gates.append(result("validity_gate", "INVALID", str(exc)))
    present = {r["check_id"] for r in gates}
    gates += [result(n, "INVALID", "ESSENTIAL_EVIDENCE_UNAVAILABLE") for n in GATES if n not in present]
    gate_status = {g["check_id"]: g["status"] for g in gates}
    trusted = all(gate_status.get(g) == "PASS" for g in ("contract", "evidence_integrity", "timeline"))
    optimizers = optimizer_results(c, trusted)
    policies = []
    for item in task_spec()["expected_items"]:
        checks = correctness(c, frames, item) if trusted else [
            result(item["sku"] + "." + name, "INVALID", "ESSENTIAL_EVIDENCE_UNAVAILABLE") for name in CORRECTNESS]
        policies.append(score_policy("ITEM." + item["sku"], checks, optimizers, terminal))
    status = aggregate(gates + policies) if terminal else "PENDING"
    return {"status": status, "reward": REWARDS[status] if terminal else None,
            "training_eligible": terminal and status != "INVALID", "rubric": identity(),
            "strict_checks": gates, "policies": policies, "shared_optimizers": optimizers,
            "policy_count": 3, "correctness_check_count": 9, "optimizer_measurement_count": 5,
            "optimizer_scope": "episode_shared", "policy_vote_role": "authoritative_after_gates",
            "reason_codes": [r["check_id"] + ":" + r["reason_code"] for r in gates if r["status"] != "PASS"] +
                            [p["policy_id"] + ":" + p["status"] for p in policies if p["status"] not in {"PASS", "PENDING"}],
            "correlation_notice": "Five shared episode budgets, referenced by three policies, not fifteen independent measurements.",
            "progress": progress(frames[-1]["state"] if frames else None, task_spec())}
