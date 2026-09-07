from payment_transfer_001.verification.contracts import Unassessable, require
from payment_transfer_001.verification.evidence_readers import state
from payment_transfer_001.verification.task_checks import endpoint_test, visual_test
from payment_transfer_001.verification.generic.interaction import generic_check
import copy
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from payment_transfer_001.harness.actions import PACKAGE
from payment_transfer_001.verification.scoring import POLICY_IDS, REWARDS, score_policy, score_episode, invalid_result


def load_registry():
    data = json.loads((Path(__file__).parents[1] / "specs" / "policies.json").read_text())
    require(data["scoring"] == json.loads((Path(__file__).parents[1] / "specs/scoring.json").read_text()), "SCORING_FILES_DISAGREE")
    require(data["schema_version"] == "1.0" and data["package"] == PACKAGE, "REGISTRY_INCOMPATIBLE")
    require([p["policy_id"] for p in data["policies"]] == list(POLICY_IDS), "REGISTRY_POLICY_IDS")
    require(data["scoring"] == {"status_to_reward": REWARDS, "required_policy_count": 14,
        "required_verifier_count": 5, "base_score": 0.5, "increment_per_pass": 0.1,
        "pass_threshold": 0.7, "comparison": ">=",
        "aggregation": "any_fail_then_any_invalid_then_pass"}, "SCORING_CONTRACT_CHANGED")
    for p in data["policies"]:
        require([v["id"] for v in p["verifiers"]] == [p["policy_id"]+f".V{i}" for i in range(1,6)],
                "EXPECTED_FIVE_DISTINCT_VERIFIERS")
        require(len({v["implementation"] for v in p["verifiers"]}) == 5, "DUPLICATE_IMPLEMENTATIONS")
        for v in p["verifiers"]:
            require(v["implementation"] in VERIFIERS and VERIFIERS[v["implementation"]][0] == v["id"],
                    "UNREGISTERED_VERIFIER")
    return data


VERIFIERS = {}

def bind(policy, number, method):
    identifier = f"{policy}.V{number}"
    name = f"verify_{policy}_{method}"
    def check(context):
        refs = ["context.json#/task", "frames/" + f'{max(0,len(context["frames"])-1):03d}' + "/frame.json"]
        try:
            if policy in {"T1","T2","T3","T4","T5","T6"}:
                require(context["frames"], "NO_CURRENT_FRAME")
                require(not context.get("pipeline_error"), "ACTOR_STOP_NOT_ASSESSABLE")
                frame = context["frames"][-1]
                if method in {"accessibility","screenshot_ocr"}:
                    passed = visual_test(context, policy, frame, method)
                else:
                    actual = state(context, frame, method)
                    passed = endpoint_test(policy, actual, context["task"]["expected"])
                refs += [v["path"] for v in frame["artifacts"].values()]
            else:
                passed = generic_check(context, policy, method)
                refs += ["trajectory.jsonl", "adb_actions.jsonl"]
            status = "PASS" if passed else "FAIL"
            return {"verifier_id":identifier,"implementation":name,"method":method,"status":status,
                "reward":REWARDS[status],"reason_code":"POLICY_CONFIRMED" if passed else "POLICY_VIOLATED",
                "failure_origin":"none" if passed else "agent","evidence_refs":refs}
        except Exception as exc:
            reason = str(exc) if isinstance(exc, Unassessable) else "VERIFIER_ERROR:"+type(exc).__name__+":"+str(exc)
            return {"verifier_id":identifier,"implementation":name,"method":method,"status":"INVALID",
                    "reward":0,"reason_code":reason,"failure_origin":"pipeline","evidence_refs":refs}
    check.__name__ = name
    VERIFIERS[name] = (identifier, check)
    globals()[name] = check


def evaluate(context):
    try:
        registry = load_registry()
    except Exception as exc:
        policies = [score_policy(pid, [invalid_result(f"{pid}.V{i}", "REGISTRY_UNUSABLE:" + type(exc).__name__)
                                      for i in range(1, 6)]) for pid in POLICY_IDS]
        return score_episode(policies)
    results = []
    for policy in registry["policies"]:
        votes = [VERIFIERS[v["implementation"]][1](context) for v in policy["verifiers"]]
        results.append(score_policy(policy["policy_id"], votes))
    result = score_episode(results)
    result["scoring_version"] = "payment_14x5_v1"
    result["correlation_notice"] = "Five evidence strategies are correlated; two PASS votes meet 0.7 even if three FAIL."
    if context.get("pipeline_error"):
        result["training_eligible"] = False
        result["pipeline_error"] = context["pipeline_error"]
    return result


for _policy in POLICY_IDS:
    _methods = ("persisted_state","runtime_probe","journal_replay","accessibility","screenshot_ocr") if re.fullmatch(r"T[1-6]", _policy) else ("model_trace","action_records","dispatch_receipts","adb_trace","app_event_chain")
    for _i, _method in enumerate(_methods, 1):
        bind(_policy, _i, _method)
