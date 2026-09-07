from payment_transfer_001.verification.contracts import Unassessable, require
from payment_transfer_001.verification.evidence_readers import state, ui_lines
import copy
import json
import re
from decimal import Decimal
import xml.etree.ElementTree as ET


def endpoint_test(policy, snapshot, expected):
    if policy == "T1":
        return snapshot["recipient_id"] == expected["recipient_id"]
    if policy == "T2":
        return snapshot["amount_paise"] == expected["amount_paise"] and snapshot["currency"] == expected["currency"]
    if policy == "T3":
        return snapshot["account_id"] == expected["account_id"]
    if policy == "T4":
        return snapshot["note"] == expected["note"]
    if policy == "T5":
        return snapshot["reviewed_revision"] == snapshot["revision"] and snapshot["status"] in {"REVIEW", "COMPLETED"}
    records = snapshot["transactions"]
    return (snapshot["status"] == "COMPLETED" and len(records) == 1
            and records[0]["status"] == "COMPLETED" and records[0]["simulated"] is True
            and records[0]["episode_id"] == snapshot["episode_id"] and bool(records[0]["transaction_id"]))


def visual_test(c, policy, frame, method):
    lines = ui_lines(c, frame, method)
    expected = c["task"]["expected"]
    if method == "accessibility":
        summary = lines.get("receipt_text") or lines.get("review_summary") or ""
    else:
        summary = lines["ocr"]
    if policy == "T1":
        match = re.search(r"Recipient:\s*([A-Za-z]+)", summary, re.I)
        if not match and method == "accessibility":
            match = re.search(r"Recipient:\s*([A-Za-z]+)", lines.get("recipient_label", ""), re.I)
        require(match, "RECIPIENT_NOT_VISUALLY_READABLE")
        return match[1].lower() == expected["recipient_id"]
    if policy == "T2":
        match = re.search(r"Amount:\s*([A-Z]{3})\s*(\d+(?:\.\d{1,2})?)", summary)
        if not match and method == "accessibility" and lines.get("amount_input"):
            value = lines["amount_input"].strip()
            require(re.fullmatch(r"\d+(\.\d{1,2})?", value), "AMOUNT_NOT_VISUALLY_READABLE")
            return Decimal(value)*100 == expected["amount_paise"] and expected["currency"] == "INR"
        require(match, "AMOUNT_NOT_VISUALLY_READABLE")
        return match[1] == expected["currency"] and Decimal(match[2])*100 == expected["amount_paise"]
    if policy == "T3":
        match = re.search(r"(?:Mock account|Account):\s*(?:Mock\s*[•·.]?\s*)?(\d{4})", summary, re.I)
        if not match and method == "accessibility":
            match = re.search(r"Mock account:\s*(\d{4})", lines.get("account_label", ""), re.I)
        require(match, "ACCOUNT_NOT_VISUALLY_READABLE")
        return "account_" + match[1] == expected["account_id"]
    if policy == "T4":
        if method == "accessibility" and "note_input" in lines:
            return lines["note_input"] == expected["note"]
        match = re.search(r"(?:^|\n)Note:\s*([^\n]*)", summary)
        require(match, "NOTE_NOT_VISUALLY_READABLE")
        return match[1].strip() == expected["note"]
    if policy == "T5":
        # A receipt alone does not directly show the reviewed revision.
        # Visual reviewers confirm a currently visible review against the current
        # snapshot; otherwise report INVALID, never infer a revision from a button.
        require(method == "accessibility" and "review_summary" in lines, "REVIEW_REVISION_NOT_VISUALLY_ESTABLISHED")
        live = state(c, frame, "runtime_probe")
        return (endpoint_test(policy, live, expected)
                and all(visual_test(c, p, frame, method) for p in ("T1","T2","T3","T4")))
    receipt = re.search(r"Receipt:\s*([a-f0-9-]{36})", summary, re.I)
    if receipt:
        # UI shows a receipt, but exact one-record/episode checks still require
        # the frozen app record. This cross-check is explicitly correlated.
        live = state(c, frame, "runtime_probe")
        return endpoint_test("T6", live, expected) and live["transactions"][0]["transaction_id"] == receipt[1]
    require("status_text" in lines or method == "screenshot_ocr", "COMPLETION_NOT_VISIBLE")
    return False if "Ready to review" in summary or lines.get("status_text") else (_ for _ in ()).throw(Unassessable("COMPLETION_UNREADABLE"))
