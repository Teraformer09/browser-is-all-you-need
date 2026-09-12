"""Versioned strict evidence gate; never calibrates grading to a desired pass rate.

The old 14x5 votes remain visible diagnostics. PASS additionally requires every
required strict claim, including reconstruction from frozen files (not independent evidence).
No action or business state is changed by this module.
"""
import hashlib
import json
import re
import shlex
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

from amazon_cart_001.harness.actions import decode, schema_error
from amazon_cart_001.harness.peach import PACKAGE, PROFILE, database_tables, permission_error, target_node, ui_nodes
from amazon_cart_001.verification.contracts import Unassessable, require
from amazon_cart_001.verification.peach import acceptance, endpoint, evaluate as legacy_evaluate, snapshot, task_spec
from amazon_cart_001.verification.scoring import POLICY_IDS, REWARDS, invalid_result, score_policy

SPEC = Path(__file__).resolve().parents[1] / "specs/strict_rubric.json"
REQUIRED = ("contract", "evidence_integrity", "timeline", "action_audit", "cart_lineage", "exact_outcome")
ERRORS = (Unassessable, AttributeError, KeyError, TypeError, ValueError, OSError, IndexError, sqlite3.Error, ET.ParseError)
FRAME_FILES = ("runtime_before.json", "runtime.json", "persisted_state.json", "database.sqlite", "ui.xml", "screen.png")


def rubric_identity():
    package = Path(__file__).resolve().parents[1]
    files = ("verification/strict.py", "verification/peach.py", "verification/scoring.py",
             "verification/contracts.py", "harness/actions.py", "harness/peach.py", "harness/device.py")
    hashes = {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in files}
    hashes["specs/strict_rubric.json"] = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    return {"id": "peach_strict_v1",
            "sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "source_hashes": hashes}


def criterion(name, status, reason, refs=()):
    return {"check_id": name, "status": status, "reward": REWARDS[status],
            "reason_code": reason, "evidence_refs": list(refs)}


def contract(c):
    require(c.get("task") == task_spec(), "TASK_SPEC_MISMATCH")
    require(re.fullmatch(r"peach_[a-f0-9]{32}", c.get("episode_id", "")) is not None, "BAD_EPISODE_ID")
    apk = c.get("installed_apk", {})
    require(apk.get("package") == PACKAGE and
            re.fullmatch(r"[a-f0-9]{64}", apk.get("sha256", "")) is not None and
            apk["sha256"] == apk.get("expected_sha256"), "APK_IDENTITY_UNAVAILABLE")
    require(not c.get("pipeline_error"), "PIPELINE_ERROR")
    require(c.get("evidence_profile") == PROFILE, "WRONG_APP_PROFILE")


def frozen_frames(c):
    root = Path(c["root"]).resolve()
    require(bool(c["frames"]), "INITIAL_FRAME_MISSING")
    verified = []
    for index, frame in enumerate(c["frames"]):
        require(type(frame["index"]) is int and frame["index"] == index and
                frame.get("stable") is True and frame["episode_id"] == c["episode_id"], "FRAME_IDENTITY_MISMATCH")
        raw = {}
        for name in FRAME_FILES:
            ref = frame["artifacts"][name]
            relative = f"frames/{index:03d}/{name}"
            require(ref["path"] == relative, "FRAME_PATH_MISMATCH")
            path = root / relative
            require(not path.is_symlink() and path.resolve().is_relative_to(root), "EVIDENCE_PATH_ESCAPE")
            require(0 < path.stat().st_size <= 20 * 1024 * 1024, "EVIDENCE_SIZE_INVALID")
            raw[name] = path.read_bytes()
            require(hashlib.sha256(raw[name]).hexdigest() == ref["sha256"], "EVIDENCE_HASH_MISMATCH")
        tables = database_tables(raw["database.sqlite"])
        require(all(json.loads(raw[n]) == tables for n in FRAME_FILES[:3]), "STATE_CHANNEL_DISAGREEMENT")
        require(frame.get("tables") == tables, "CONTEXT_STATE_DISAGREEMENT")
        png = raw["screen.png"]
        require(png.startswith(b"\x89PNG\r\n\x1a\n") and len(png) >= 33 and png[12:16] == b"IHDR", "PNG_INVALID")
        width, height = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
        require(0 < width <= 8192 and 0 < height <= 8192, "PNG_DIMENSIONS_INVALID")
        nodes = ui_nodes(raw["ui.xml"], tables["products"])
        require(bool(nodes) and nodes == frame.get("ui"), "UI_METADATA_DISAGREEMENT")
        # Never use the mutable context's cached derived state as ground truth.
        state = snapshot(tables, c["episode_id"])
        verified.append({**frame, "tables": tables, "ui": nodes, "state": state,
                         "width": width, "height": height})
    return verified


def timeline(c, frames):
    transitions = c["transitions"]
    require(len(frames) == len(transitions) + 1, "FRAME_COUNT_MISMATCH")
    initial = frames[0]["tables"]
    require(not initial["cart"] and not initial["search_history"] and
            not any(e["kind"] != "reset" for e in initial["eval_events"]) and
            len(initial["eval_events"]) == 1, "INITIAL_STATE_NOT_CLEAN")
    catalog = initial["products"]
    require(len({p["id"] for p in catalog}) == len(catalog) == len({p["sku"] for p in catalog}), "DUPLICATE_PRODUCT_IDENTITY")
    last_end, covered = 0, set()
    for i, transition in enumerate(transitions):
        before, after = frames[i], frames[i + 1]
        require(type(transition["step"]) is int and transition["step"] == i + 1 and
                type(transition["before_frame"]) is int and transition["before_frame"] == i and
                type(transition["after_frame"]) is int and transition["after_frame"] == i + 1,
                "TRANSITION_FRAME_BINDING_INVALID")
        old, new = before["tables"]["eval_events"], after["tables"]["eval_events"]
        require(new[:len(old)] == old, "JOURNAL_REWRITTEN")
        require(after["tables"]["products"] == catalog, "CATALOG_CHANGED_DURING_EPISODE")
        start, end = transition["trace_start"], transition["trace_end"]
        require(type(start) is int and type(end) is int and last_end <= start <= end <= len(c["adb_trace"]),
                "TRACE_RANGE_INVALID")
        covered.update(range(start, end))
        last_end = end
    require(covered == {i for i, e in enumerate(c['adb_trace']) if e.get('phase') == 'action'},
            'UNBOUND_ACTION_TRACE')
    return len(transitions) <= c["task"]["max_steps"]


def expected_inputs(action, node, transport=None):
    kind = action["type"]
    if kind in {"tap_element", "type_text"}:
        left, top, right, bottom = node["bounds"]
        commands = [["shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2)]]
        if kind == "type_text":
            commands += [["shell", "input", "keycombination", "113", "29"],
                         ["shell", "input", "keyevent", "KEYCODE_DEL"]]
            if action["text"]:
                chunks = action["text"] if transport in {"persisted_text_chars_v1", "persisted_text_chars_v2"} else [action["text"]]
                commands.extend(["shell", "input", "text", shlex.quote(chunk.replace(" ", "%s"))] for chunk in chunks)
            commands.append(["shell", "input", "keyevent", "KEYCODE_BACK"])
        return commands
    if kind == "swipe":
        return [["shell", "input", "swipe", *[str(action[k]) for k in ("x1", "y1", "x2", "y2", "duration_ms")]]]
    if kind == "press_back":
        return [["shell", "input", "keyevent", "KEYCODE_BACK"]]
    return []


def dispatch_trace(c, transition, before, trace):
    """Bind the just-before-action UI dump to the ADB stdout receipt."""
    ref = transition.get("dispatch_artifact")
    if ref is None:
        require(not transition["receipt"]["executed"] or transition["action"]["type"] not in
                {"tap_element", "type_text"}, "DISPATCH_XML_MISSING")
        return before["ui"], trace
    root = Path(c["root"]).resolve()
    relative = f"dispatch/{transition['step']:03d}.xml"
    require(ref["path"] == relative, "DISPATCH_PATH_MISMATCH")
    path = root / relative
    require(not path.is_symlink() and path.resolve().is_relative_to(root) and
            0 < path.stat().st_size <= 20 * 1024 * 1024, "DISPATCH_PATH_OR_SIZE_INVALID")
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    require(sha == ref["sha256"], "DISPATCH_HASH_MISMATCH")
    nodes = ui_nodes(raw, before["tables"]["products"])
    require(nodes == transition["dispatch_ui"], "DISPATCH_METADATA_DISAGREEMENT")
    retries = 0
    while trace and trace[0].get("stderr", "").strip() == "ERROR: null root node returned by UiTestAutomationBridge.":
        retries += 1
        require(retries <= 2 and len(trace) >= 2, "DISPATCH_RETRY_LIMIT")
        failed, cleanup = trace[:2]
        command = failed["args"]
        require(len(command) == 4 and command[:3] == ["shell", "uiautomator", "dump"] and
                re.fullmatch(r"/sdcard/peach-ui-[a-f0-9]{32}\.xml", command[3]) is not None and
                failed.get("returncode") == 0 and failed.get("bytes") == 0 and
                failed.get("sha256") == hashlib.sha256(b"").hexdigest() and
                cleanup["args"] == ["shell", "rm", "-f", command[3]] and
                cleanup.get("returncode") == 0, "DISPATCH_RETRY_RECEIPT_MISMATCH")
        trace = trace[2:]
    require(len(trace) >= 3, "DISPATCH_TRACE_MISSING")
    dump = trace[0]["args"]
    require(len(dump) == 4 and dump[:3] == ["shell", "uiautomator", "dump"] and
            re.fullmatch(r"/sdcard/peach-ui-[a-f0-9]{32}\.xml", dump[3]) is not None,
            "DISPATCH_COMMAND_UNEXPECTED")
    require(trace[1]["args"] == ["exec-out", "cat", dump[3]] and
            trace[1].get("sha256") == sha and trace[1].get("bytes") == len(raw) and
            trace[2]["args"] == ["shell", "rm", "-f", dump[3]], "DISPATCH_RECEIPT_MISMATCH")
    return nodes, trace[3:]



def text_readback_trace(c, transition, inputs):
    """Remove only hash-bound, fixed-URI read probes; keep all input validation."""
    records = transition.get("input_readbacks", [])
    marker = transition["receipt"].get("input_readback_contract")
    if marker is None:
        require(not records, "UNDECLARED_INPUT_READBACK")
        return inputs
    action = transition["action"]
    require(marker in {"persisted_text_v1", "persisted_text_chars_v1", "persisted_text_chars_v2"} and schema_error(action) is None and
            action["type"] == "type_text" and 2 <= len(records) <= 10, "BAD_INPUT_READBACK_CONTRACT")
    offset = transition["trace_end"] - len(inputs)
    # v2: bounded read-only focus probes between the tap and the clear/typing
    # commands. Each probe is a hash-bound dump/cat/rm triple with a declared
    # artifact; probes never carry input commands.
    probes = transition.get("focus_probes", [])
    probe_positions = []
    if marker == "persisted_text_chars_v2":
        require(1 <= len(probes) <= 6, "FOCUS_PROBE_CONTRACT")
        for k, probe in enumerate(probes):
            position = probe.get("trace_index")
            position = position - offset if type(position) is int else -1
            require(1 <= position <= len(inputs) - 2, "FOCUS_PROBE_TRACE_RANGE")
            dump, cat, rm = inputs[position - 1:position + 2]
            require(len(dump["args"]) == 4 and dump["args"][:3] == ["shell", "uiautomator", "dump"] and
                    re.fullmatch(r"/sdcard/peach-ui-[a-f0-9]{32}\.xml", dump["args"][3]) is not None and
                    cat["args"] == ["exec-out", "cat", dump["args"][3]] and
                    rm["args"] == ["shell", "rm", "-f", dump["args"][3]], "FOCUS_PROBE_COMMANDS")
            ref = probe.get("artifact", {})
            relative = f"input_readback/focus-{transition['step']:03d}-{k:02d}.xml"
            path = Path(c["root"]).resolve() / relative
            require(ref.get("path") == relative and not path.is_symlink() and
                    path.resolve().is_relative_to(Path(c["root"]).resolve()) and
                    0 <= path.stat().st_size <= 20 * 1024 * 1024, "FOCUS_PROBE_PATH_INVALID")
            raw = path.read_bytes()
            require(cat.get("sha256") == hashlib.sha256(raw).hexdigest() == ref.get("sha256") and
                    cat.get("bytes") == len(raw), "FOCUS_PROBE_RECEIPT_MISMATCH")
            require(not raw or ET.fromstring(raw) is not None, "FOCUS_PROBE_XML_INVALID")
            if raw:
                focused = any(n.get("resource_id", "").endswith(":id/etSearchBox") and n.get("focused")
                              for n in ui_nodes(raw, c["frames"][0]["tables"]["products"]))
                require(focused == probe.get("focused"), "FOCUS_PROBE_CLAIM_MISMATCH")
            probe_positions.extend((position - 1, position, position + 1))
        require(probe_positions == sorted(probe_positions), "FOCUS_PROBE_ORDER")
        require(probes[-1].get("focused") is True, "FOCUS_NEVER_CONFIRMED")
    else:
        require(not probes, "UNDECLARED_FOCUS_PROBES")
    positions, stages = [], []
    root = Path(c["root"]).resolve()
    provider = ["shell", "content", "query", "--uri", "content://" + PACKAGE + ".verifier/state"]
    before_count = 3 + (len(action["text"]) if marker in {"persisted_text_chars_v1", "persisted_text_chars_v2"} else int(bool(action["text"])))
    for index, record in enumerate(records):
        position = record["trace_index"] - offset
        require(type(record["trace_index"]) is int and 0 <= position < len(inputs) and
                (not positions or position > positions[-1]), "INPUT_READBACK_TRACE_RANGE")
        entry, ref = inputs[position], record["artifact"]
        relative = f"input_readback/{transition['step']:03d}-{index:02d}.txt"
        path = root / relative
        require(ref["path"] == relative and not path.is_symlink() and path.resolve().is_relative_to(root) and
                0 <= path.stat().st_size <= 20 * 1024 * 1024, "INPUT_READBACK_PATH_INVALID")
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        require(entry["args"] == provider and ref["sha256"] == entry.get("sha256") == sha and
                entry.get("bytes") == len(raw), "INPUT_READBACK_RECEIPT_MISMATCH")
        if record.get("error_code") == "PROVIDER_SNAPSHOT_UNAVAILABLE":
            require(raw == b"" and entry.get("returncode") == 0 and
                    "java.lang.IllegalStateException: Read-only snapshot unavailable" in entry.get("stderr", "") and
                    record["expected"] == action["text"] and record["actual"] is None and
                    record["episode_id"] is None and record["confirmed"] is False,
                    "INPUT_READBACK_UNAVAILABLE_CLAIM_MISMATCH")
        else:
            require(record.get("error_code") is None, "INPUT_READBACK_UNKNOWN_ERROR")
            text = raw.decode()
            require("snapshot=" in text, "INPUT_READBACK_RESPONSE_UNREADABLE")
            sessions = json.loads(text.split("snapshot=", 1)[1].strip())["eval_session"]
            require(len(sessions) == 1 and sessions[0]["episode_id"] == c["episode_id"] and
                    isinstance(sessions[0]["draft"], str), "INPUT_READBACK_EPISODE_MISMATCH")
            state = sessions[0]
            confirmed = state["draft"] == action["text"]
            require(record["expected"] == action["text"] and record["actual"] == state["draft"] and
                    record["episode_id"] == c["episode_id"] and record["confirmed"] is confirmed,
                    "INPUT_READBACK_CLAIM_MISMATCH")
        stage = record["stage"]
        require(stage in {"before_dismiss", "after_dismiss"}, "INPUT_READBACK_STAGE")
        sent = sum(e["args"][:2] == ["shell", "input"] for e in inputs[:position])
        require(sent == before_count + int(stage == "after_dismiss"), "INPUT_READBACK_ORDER")
        stages.append(stage)
        positions.append(position)
    require(stages == sorted(stages, key=lambda stage: stage == "after_dismiss"), "INPUT_READBACK_STAGE_ORDER")
    for stage in ("before_dismiss", "after_dismiss"):
        group = [r for r in records if r["stage"] == stage]
        require(1 <= len(group) <= 5 and group[-1]["confirmed"] is True and
                all(r["confirmed"] is False for r in group[:-1]), "INPUT_READBACK_NOT_CONFIRMED")
    excluded = set(positions) | set(probe_positions)
    return [entry for index, entry in enumerate(inputs) if index not in excluded]

def action_audit(c, frames):
    passed = True
    wanted = {p["sku"] for p in c["task"]["expected_items"]}
    for i, transition in enumerate(c["transitions"]):
        action, receipt = transition["action"], transition["receipt"]
        require(decode(transition["raw_response"]) == action, "RAW_ACTION_MISMATCH")
        schema_ok = schema_error(action) is None
        permitted = permission_error(action) is None
        require(receipt.get("schema_valid") is schema_ok and receipt.get("permitted") is permitted,
                "ACTION_VALIDITY_RECEIPT_CONTRADICTION")
        require(all(type(receipt.get(k)) is bool for k in ("executed", "accepted", "execution_receipt")),
                "MALFORMED_ACTION_RECEIPT")
        require(receipt.get("failure_origin") in {"none", "agent", "pipeline"}, "FAILURE_ORIGIN_MISSING")
        require(receipt["failure_origin"] != "pipeline", "ACTION_TRANSPORT_UNASSESSABLE")
        require(receipt["executed"] is receipt["execution_receipt"] and
                (receipt["executed"] or not receipt["accepted"]), "EXECUTION_RECEIPT_CONTRADICTION")
        before, after = frames[i], frames[i + 1]
        trace = c["adb_trace"][transition["trace_start"]:transition["trace_end"]]
        require(all(e.get("phase") == "action" and e.get("returncode") == 0 and not e.get("error")
                    for e in trace), "ADB_TRACE_UNASSESSABLE")
        dispatch, inputs = dispatch_trace(c, transition, before, trace)
        inputs = text_readback_trace(c, transition, inputs)
        operations = [e for e in after["tables"]["eval_events"][len(before["tables"]["eval_events"]):]
                      if e["kind"] in {"search", "add", "decrease", "remove"}]
        if not receipt["executed"]:
            require(not inputs and not operations, "REJECTED_ACTION_CHANGED_STATE")
            require(receipt["failure_origin"] == "agent" and bool(receipt.get("error")), "REJECTION_REASON_MISSING")
            passed = False
            continue
        require(schema_ok and permitted, "INVALID_ACTION_WAS_EXECUTED")
        try:
            target_node(action, before["ui"])
            node = target_node(action, dispatch)
        except ValueError as error:
            raise Unassessable("EXECUTED_TARGET_UNAVAILABLE") from error
        if node:
            left, top, right, bottom = node["bounds"]
            require(0 <= left < right <= before["width"] and 0 <= top < bottom <= before["height"],
                    "DISPATCH_BOUNDS_INVALID")
        require([e["args"] for e in inputs] == expected_inputs(action, node, receipt.get("input_readback_contract")), "ADB_ACTION_RECEIPT_MISMATCH")
        accepted = acceptance(action, before, after)
        require(receipt["accepted"] is accepted, "APP_ACCEPTANCE_RECEIPT_CONTRADICTION")
        if accepted:
            require(receipt["failure_origin"] == "none" and not receipt.get("error"), "ACCEPTED_ACTION_HAS_ERROR")
        else:
            require(receipt["failure_origin"] == "agent" and bool(receipt.get("error")), "REJECTION_REASON_MISSING")
            passed = False
        target = action.get("element_id", "")
        # Keep the original S1 constraint: adding an extra product is a wrong selection,
        # even if a later removal makes the final cart correct.
        if target.startswith(("add_", "increase_")) and target.split("_", 1)[1] not in wanted:
            passed = False
        if action["type"] == "swipe":
            if not all(0 <= action[k] < limit for k, limit in
                       (("x1", before["width"]), ("x2", before["width"]),
                        ("y1", before["height"]), ("y2", before["height"]))):
                passed = False
        if action["type"] == "press_back" and before["state"]["page"] == "home":
            passed = False
        expected_count = int(accepted and (target == "search_button" or
                             target.startswith(("add_", "increase_", "decrease_", "remove_"))))
        require(len(operations) == expected_count, "UNEXPLAINED_OR_DUPLICATE_APP_MUTATION")
        if action["type"] == "finish" and i != len(c["transitions"]) - 1:
            passed = False
    return passed

def cart_lineage(tables, task):
    """Each currently present SKU must have entered its current cart interval via search.

    An interval begins at zero->positive quantity and ends at removal/zero.
    Identical units have no invented FIFO/LIFO identity. Removing and re-adding
    starts a new interval, which needs its own valid search context.
    """
    products = {p["id"]: p for p in tables["products"]}
    quantities, origins, current, page, query = {}, {}, None, "home", ""
    for event in tables["eval_events"]:
        kind, data = event["kind"], json.loads(event["payload"])
        if kind == "viewport":
            page, query = data["page"], data["query"]
        elif kind == "search":
            query = data["query"]
            current = (event["sequence"], query)
        elif kind in {"add", "decrease", "remove"}:
            product = products[data["product_id"]]
            sku, quantity = product["sku"], data["quantity_after"]
            previous = quantities.get(sku, 0)
            if kind == "add" and previous == 0:
                text = (product["name"] + " " + product["category"] + " " + sku).lower()
                eligible = (current and page in {"results", "detail"} and query == current[1] and
                            all(word in text for word in query.lower().split()))
                origins[sku] = current[0] if eligible else None
            if quantity:
                quantities[sku] = quantity
            else:
                quantities.pop(sku, None)
                origins.pop(sku, None)
    wanted = {p["sku"]: p["quantity"] for p in task["expected_items"]}
    if quantities != wanted:
        return False
    sources = [origins.get(sku) for sku in wanted]
    return all(source is not None for source in sources) and len(set(sources)) == len(wanted)

def visible_summary(frames):
    checked = 0
    for frame in frames:
        if frame["state"]["page"] != "cart":
            continue
        state = frame["state"]
        paise = state['subtotal_paise']
        amount = f"₹{paise // 100:,}" + (f".{paise % 100:02d}" if paise % 100 else "")
        expected = f"Subtotal ({state['cart_count']} items): {amount}"
        matches = [n["text"] for n in frame["ui"] if n["text"].startswith("Subtotal (")]
        if matches:
            require(len(matches) == 1 and matches[0] == expected, "VISIBLE_SUBTOTAL_CONTRADICTS_STATE")
            checked += 1
    return criterion("visible_cart_summary", "PASS" if checked else "INVALID",
                     "VISIBLE_SUMMARY_CONFIRMED" if checked else "SUMMARY_OFFSCREEN_OPTIONAL", ["frames/*/ui.xml"])


def evaluate(c):
    checks, spec = [], {}
    identity = {"id": "peach_strict_v1", "sha256": None}
    try:
        legacy = legacy_evaluate(c)
    except ERRORS:
        legacy = {"policies": [score_policy(p, [invalid_result(f"{p}.V{i}", "LEGACY_EVIDENCE_UNAVAILABLE")
                                               for i in range(1, 6)]) for p in POLICY_IDS]}
    diagnostic = criterion("visible_cart_summary", "INVALID", "REQUIRED_EVIDENCE_UNAVAILABLE")
    try:
        spec = json.loads(SPEC.read_text())
        require(spec["rubric_id"] == "peach_strict_v1" and
                spec["required_checks"] == list(REQUIRED) and spec["status_to_reward"] == REWARDS,
                "WRONG_STRICT_RUBRIC")
        identity = rubric_identity()
        contract(c)
        checks.append(criterion("contract", "PASS", "SPEC_AND_APK_CONFIRMED", ["installed_apk.json"]))
        frames = frozen_frames(c)
        checks.append(criterion("evidence_integrity", "PASS", "ALL_REQUIRED_CHANNELS_AGREE", ["frames/*"]))
        claims = (("timeline", lambda: timeline(c, frames)),
                  ("action_audit", lambda: action_audit(c, frames)),
                  ("cart_lineage", lambda: cart_lineage(frames[-1]["tables"], c["task"])),
                  ("exact_outcome", lambda: all(endpoint(p, frames[-1]["state"], c["task"])
                                                for p in ("T1", "T2", "T3", "T4", "T5", "T6"))))
        for name, check in claims:
            try:
                result = check()
                checks.append(criterion(name, "PASS" if result else "FAIL",
                              "CLAIM_CONFIRMED" if result else "REQUIRED_CLAIM_UNMET", ["context.json", "frames/*"]))
            except ERRORS as error:
                checks.append(criterion(name, "INVALID", str(error) or type(error).__name__, ["context.json", "frames/*"]))
                # Later action checks depend on valid frame/trace bindings.
                if name == "timeline":
                    break
        diagnostic = visible_summary(frames)
    except ERRORS as error:
        checks.append(criterion("required_evidence_gate", "INVALID",
                      str(error) or type(error).__name__, ["context.json", "frames/*"]))
    present = {r["check_id"] for r in checks}
    checks.extend(criterion(name, "INVALID", "REQUIRED_CHECK_NOT_ASSESSABLE") for name in REQUIRED if name not in present)
    # Conclusive trusted failures win; otherwise unassessable evidence prevents PASS.
    status = "FAIL" if any(r["status"] == "FAIL" for r in checks) else (
             "INVALID" if any(r["status"] == "INVALID" for r in checks) else "PASS")
    return {"status": status, "reward": REWARDS[status], "training_eligible": status != "INVALID",
            "reason_codes": [r["check_id"] + ":" + r["reason_code"] for r in checks if r["status"] != "PASS"],
            "rubric": identity, "strict_checks": checks, "diagnostics": [diagnostic],
            "policies": legacy["policies"], "legacy_vote_status": legacy.get("status", "INVALID"),
            "policy_vote_role": "diagnostic_only", "policy_count": 14, "verifier_count": 70,
            "evidence_profile": PROFILE, "correlation_notice": spec.get("evidence_notice", "Specification unavailable")}
