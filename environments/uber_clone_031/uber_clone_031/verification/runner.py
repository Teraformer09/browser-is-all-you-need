"""Run all registered verifiers once at actor-stop; never sum their signed votes."""
from __future__ import annotations

import jsonschema
from uber_clone_031.verification.registry import load_registry
from uber_clone_031.verification.scoring import POLICY_IDS, invalid_result, score_episode, score_policy
from uber_clone_031.verification.checks import VERIFIERS


def task_expectations(task):
    return {"pickup": task.pickup, "ride_type": task.ride_type, "destination": task.destination,
            "cab_type": task.selected_ride, "payment_method": task.payment,
            "cancel_after_assignment": task.cancel_after_assignment}


def verify_episode(context):
    try:
        registry = context.get("registry") or load_registry()
    except Exception as exc:
        policies = [score_policy(pid, [invalid_result(f"{pid}.V{i}", "REGISTRY_UNUSABLE:" + type(exc).__name__)
                                      for i in range(1, 6)]) for pid in POLICY_IDS]
        return {**score_episode(policies), "registry_sha256": None}
    context = {**context, "registry": registry}
    if context.get("registry_valid") is not True or context.get("task_expected") != registry["task"]["expected"]:
        policies = [score_policy(pid, [invalid_result(f"{pid}.V{i}", "TASK_SPECIFICATION_UNUSABLE")
                                      for i in range(1, 6)]) for pid in POLICY_IDS]
        return {**score_episode(policies), "registry_sha256": registry["sha256"]}
    validator = jsonschema.Draft202012Validator(registry["result_schema"])
    policies = []
    for policy in registry["policies"]:
        results = []
        for entry in policy["verifiers"]:
            binding = VERIFIERS.get(entry["implementation"])
            if binding is None or binding[0] != entry["id"]:
                result = invalid_result(entry["id"], "VERIFIER_IMPLEMENTATION_UNAVAILABLE")
            else:
                result = binding[1](context)
            if list(validator.iter_errors(result)):
                result = invalid_result(entry["id"], "RESULT_SCHEMA_INVALID")
            results.append(result)
        policies.append(score_policy(policy["policy_id"], results))
    return {**score_episode(policies), "registry_sha256": registry["sha256"],
            "scoring_id": registry["scoring"]["scoring_id"], "assessment_point": "actor_stop"}
