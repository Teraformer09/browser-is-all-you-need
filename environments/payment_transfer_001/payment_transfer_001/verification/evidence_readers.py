from payment_transfer_001.verification.contracts import Unassessable, require
import copy
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from payment_transfer_001.harness.evidence import digest, prefs_snapshot, nodes
from payment_transfer_001.verification.records import verify as record_verify


def artifact(c, frame, name, mode="json"):
    ref = frame.get("artifacts", {}).get(name)
    require(isinstance(ref, dict), "EVIDENCE_MISSING:" + name)
    path = (Path(c["root"]) / ref["path"]).resolve()
    require(path.is_relative_to(Path(c["root"]).resolve()), "EVIDENCE_PATH_ESCAPE")
    data = path.read_bytes()
    require(digest(data) == ref["sha256"], "EVIDENCE_HASH_MISMATCH:" + name)
    return json.loads(data) if mode == "json" else data.decode() if mode == "text" else data


def state_valid(c, state):
    require(record_verify(state, c["task"], c["episode_id"])["status"] != "INVALID", "STATE_SCHEMA_OR_EPISODE_INVALID")
    return state


def state(c, frame, method):
    require(frame.get("stable") is True and not frame.get("errors"), "FRAME_NOT_STABLE")
    if method == "persisted_state":
        result = prefs_snapshot(artifact(c, frame, "preferences.xml", "text"))
    elif method == "runtime_probe":
        result = artifact(c, frame, "runtime.json")
    elif method == "journal_replay":
        events = artifact(c, frame, "journal.json")
        require(events and events[0]["action"] == "open" and events[0]["state"]["revision"] == 0
                and not events[0]["state"]["transactions"], "JOURNAL_INITIALIZATION_MISSING")
        previous = events[0]["state"]
        allowed_changes = {
            "select_recipient": {"recipient_id", "revision", "reviewed_revision", "status"},
            "select_account": {"account_id", "revision", "reviewed_revision", "status"},
            "enter_amount": {"amount_input", "amount_paise", "revision", "reviewed_revision", "status"},
            "enter_note": {"note", "revision", "reviewed_revision", "status"},
            "review": {"reviewed_revision", "status"}, "confirm": {"transactions", "status"},
            "open": set()}
        for i, event in enumerate(events):
            require(event.get("sequence") == i and type(event.get("accepted")) is bool, "JOURNAL_GAP")
            current = state_valid(c, event["state"])
            kind = event["action"]
            require(kind in allowed_changes, "UNKNOWN_APP_EVENT")
            changed = {k for k in current if current.get(k) != previous.get(k)}
            require(changed <= (allowed_changes[kind] if event["accepted"] else set()), "UNEXPLAINED_MUTATION")
            if i and kind in {"select_recipient","select_account","enter_amount","enter_note"} and changed:
                require(current["revision"] == previous["revision"]+1 and current["reviewed_revision"] == -1,
                        "REVISION_REPLAY_MISMATCH")
            if kind == "confirm" and event["accepted"]:
                require(previous["reviewed_revision"] == previous["revision"]
                        and current["reviewed_revision"] == current["revision"], "UNREVIEWED_COMMIT")
            previous = copy.deepcopy(current)
        result = previous
    else:
        raise Unassessable("UNKNOWN_STATE_CHANNEL")
    return state_valid(c, result)


def ui_lines(c, frame, method):
    require(frame.get("stable") is True and not frame.get("errors"), "VISUAL_FRAME_NOT_ATTRIBUTABLE")
    if method == "accessibility":
        ui = nodes(artifact(c, frame, "ui.xml", "text"))
        return {n["id"]: n["text"] for n in ui if n["id"]}
    ocr = artifact(c, frame, "ocr.json")
    png = artifact(c, frame, "screen.png", "bytes")
    require(ocr["source_sha256"] == digest(png), "OCR_IMAGE_MISMATCH")
    # Reconstruct lines from OCR's own pixel-derived word boxes, not UI node text.
    groups = {}
    for word in ocr["words"]:
        if float(word.get("conf", -1)) >= 70:
            key = tuple(word.get(k) for k in ("block_num", "par_num", "line_num"))
            groups.setdefault(key, []).append(word["text"])
    return {"ocr": "\n".join(" ".join(words) for words in groups.values())}
