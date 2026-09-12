"""Exact user-specified 14-policy / five-verifier ternary scoring contract."""
from __future__ import annotations

POLICY_IDS = ("V1", "V2", "V15", "G1", "G2", "G3", "G4", "S1", "T1", "T2", "T3", "T4", "T5", "T6", "T7")
REWARDS = {"PASS": 1, "INVALID": 0, "FAIL": -1}


def invalid_result(identifier, reason, refs=()):
    return {"verifier_id": identifier, "status": "INVALID", "reward": 0,
            "reason_code": reason, "failure_origin": "pipeline", "evidence_refs": list(refs)}


def score_policy(policy_id, results):
    expected = {f"{policy_id}.V{i}" for i in range(1, 6)}
    errors = []
    if policy_id not in POLICY_IDS:
        errors.append("UNKNOWN_POLICY_ID")
    if not isinstance(results, list) or len(results) != 5:
        errors.append("EXPECTED_FIVE_VERIFIERS")
        results = []
    if any(not isinstance(r, dict) or not isinstance(r.get("verifier_id"), str) for r in results) or {r.get("verifier_id") for r in results if isinstance(r, dict) and isinstance(r.get("verifier_id"), str)} != expected:
        errors.append("MISSING_DUPLICATE_OR_UNEXPECTED_VERIFIER_ID")
    for result in results:
        if not isinstance(result, dict):
            errors.append("MALFORMED_VERIFIER_RESULT")
            continue
        value = result.get("reward")
        if type(value) not in (int, float) or value not in (-1, 0, 1) or REWARDS.get(result.get("status")) != value:
            errors.append("STATUS_REWARD_MISMATCH")
        if not isinstance(result.get("reason_code"), str) or not result["reason_code"]:
            errors.append("MISSING_REASON")
        if not isinstance(result.get("evidence_refs"), list):
            errors.append("MISSING_EVIDENCE_REFERENCES")
    if errors:
        return {"policy_id": policy_id, "status": "INVALID", "reward": 0, "policy_score": None,
                "verifier_results": results, "reason_codes": sorted(set(errors)), "input_valid": False,
                "passed_verifiers": 0, "failed_verifiers": 0, "invalid_verifiers": 5}
    passed = sum(r["reward"] == 1 for r in results)
    failed = sum(r["reward"] == -1 for r in results)
    invalid = 5 - passed - failed
    score_tenths = 5 + passed
    status = "INVALID" if invalid == 5 else "PASS" if score_tenths >= 7 else "FAIL"
    return {"policy_id": policy_id, "status": status, "reward": REWARDS[status],
            "policy_score": score_tenths / 10, "passed_verifiers": passed, "failed_verifiers": failed,
            "invalid_verifiers": invalid, "verifier_results": results,
            "conflicting_verdicts": passed > 0 and failed > 0, "input_valid": True,
            "reason_codes": ["ALL_VERIFIERS_INVALID" if invalid == 5 else
                             "PASS_THRESHOLD_MET" if status == "PASS" else "INSUFFICIENT_PASS_VOTES"]}


def score_episode(policy_results):
    if not isinstance(policy_results, list) or len(policy_results) != len(POLICY_IDS) or {
        p.get("policy_id") for p in policy_results if isinstance(p, dict)
    } != set(POLICY_IDS):
        return {"status": "INVALID", "reward": 0, "training_eligible": False,
                "reason_codes": ["EXPECTED_POLICY_SET_MISMATCH"], "policies": policy_results}
    malformed = any(type(p.get("reward")) not in (int, float) or REWARDS.get(p.get("status")) != p.get("reward")
                    for p in policy_results)
    if malformed:
        return {"status": "INVALID", "reward": 0, "training_eligible": False,
                "reason_codes": ["MALFORMED_POLICY_RESULT"], "policies": policy_results}
    statuses = [p["status"] for p in policy_results]
    status = "FAIL" if "FAIL" in statuses else "INVALID" if "INVALID" in statuses else "PASS"
    return {"status": status, "reward": REWARDS[status], "training_eligible": status != "INVALID",
            "reason_codes": [p["policy_id"] + ":" + p["status"] for p in policy_results if p["status"] != "PASS"],
            "policies": policy_results, "policy_count": len(POLICY_IDS), "verifier_count": 5 * len(POLICY_IDS),
            "conflicting_policy_count": sum(bool(p.get("conflicting_verdicts")) for p in policy_results)}


def training_rewards(verdicts):
    """Explicit filter for consumers BEFORE normalization/advantages; never bool(reward)."""
    eligible = []
    for verdict in verdicts:
        status = verdict.get("status")
        if status not in REWARDS or type(verdict.get("reward")) not in (int, float) or verdict["reward"] != REWARDS[status]:
            raise ValueError("Missing or inconsistent verdict; do not consume a default zero")
        if verdict.get("training_eligible") != (status != "INVALID"):
            raise ValueError("Training eligibility does not match the verdict")
        if verdict["training_eligible"]:
            eligible.append(verdict["reward"])
    return eligible
