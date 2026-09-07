"""Initial deterministic transaction checker, not the Uber-031 70-verifier layer."""
from __future__ import annotations

EXPECTED_FIELDS = ("recipient_id", "amount_paise", "currency", "account_id", "note")
REQUIRED_FIELDS = ("schema_version", "episode_id", "simulated", "status", "revision",
                   "reviewed_revision", "transactions", *EXPECTED_FIELDS)

def verdict(status, reason, checks=None):
    return {"status": status, "reward": {"PASS": 1, "INVALID": 0, "FAIL": -1}[status],
            "reason": reason, "checks": checks or {}, "training_eligible": status != "INVALID",
            "verifier_version": "payment-record-v1", "policy_layer": "not_14x5"}

def verify(snapshot, task, episode_id):
    if not isinstance(task, dict) or not isinstance(task.get("expected"), dict):
        return verdict("INVALID", "TASK_SPECIFICATION_UNAVAILABLE")
    expected = task["expected"]
    if any(key not in expected for key in EXPECTED_FIELDS) or type(expected.get("amount_paise")) is not int or expected.get("amount_paise", 0) <= 0 or not all(isinstance(expected.get(k), str) and expected[k] for k in ("recipient_id", "currency", "account_id")) or not isinstance(expected.get("note"), str):
        return verdict("INVALID", "TASK_SPECIFICATION_INVALID")
    if not isinstance(snapshot, dict) or any(key not in snapshot for key in REQUIRED_FIELDS):
        return verdict("INVALID", "STATE_SCHEMA_INCOMPLETE")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1 or snapshot["episode_id"] != episode_id or snapshot["simulated"] is not True:
        return verdict("INVALID", "STATE_IDENTITY_MISMATCH")
    if type(snapshot["revision"]) is not int or type(snapshot["reviewed_revision"]) is not int:
        return verdict("INVALID", "REVISION_UNREADABLE")
    if type(snapshot["amount_paise"]) is not int or not all(isinstance(snapshot[k], str) for k in ("recipient_id", "currency", "account_id", "note")):
        return verdict("INVALID", "DRAFT_FIELDS_UNREADABLE")
    records = snapshot["transactions"]
    if not isinstance(records, list) or snapshot["status"] not in {"DRAFT", "REVIEW", "COMPLETED"}:
        return verdict("INVALID", "TRANSACTION_STATE_UNREADABLE")
    checks = {key: snapshot[key] == expected[key] for key in EXPECTED_FIELDS}
    checks["reviewed"] = snapshot["reviewed_revision"] == snapshot["revision"]
    checks["exactly_one_transaction"] = len(records) == 1
    if not records:
        return verdict("FAIL", "NO_COMMITTED_TRANSFER", checks)
    if len(records) != 1:
        return verdict("FAIL", "DUPLICATE_TRANSFERS", checks)
    tx = records[0]
    required = {*EXPECTED_FIELDS, "transaction_id", "episode_id", "status", "simulated", "reviewed_revision"}
    if not isinstance(tx, dict) or not required.issubset(tx) or type(tx.get("amount_paise")) is not int or type(tx.get("reviewed_revision")) is not int:
        return verdict("INVALID", "TRANSACTION_RECORD_UNREADABLE", checks)
    if not all(isinstance(tx[k], str) for k in ("recipient_id", "currency", "account_id", "note", "transaction_id", "episode_id", "status")):
        return verdict("INVALID", "TRANSACTION_FIELD_TYPES_INVALID", checks)
    checks.update({"committed_" + key: tx[key] == expected[key] for key in EXPECTED_FIELDS})
    checks["receipt"] = bool(tx["transaction_id"])
    checks["episode"] = tx["episode_id"] == episode_id
    checks["completed"] = tx["status"] == snapshot["status"] == "COMPLETED"
    checks["simulated"] = tx["simulated"] is True
    checks["review_matches_record"] = tx["reviewed_revision"] == snapshot["reviewed_revision"] == snapshot["revision"]
    return verdict("PASS" if all(checks.values()) else "FAIL",
                   "CORRECT_SIMULATED_TRANSFER" if all(checks.values()) else "TRANSFER_MISMATCH", checks)
