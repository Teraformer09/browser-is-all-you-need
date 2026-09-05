"""Versioned, allowlisted JSON registry. Agent text cannot replace these policies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
from uber_clone_031.verification.scoring import POLICY_IDS


def specs_root():
    return Path(__file__).parents[1] / "specs"


def load_registry(root=None):
    root = Path(root) if root else specs_root()
    def read(name):
        return json.loads((root / name).read_text())
    app, topic = read("apps/uber_clone/manifest.json"), read("topics/ride_booking/rules.json")
    source = read("task.json")
    p = source["parameters"]
    task = {**source["verifier_contract"], "task_id": source["task_id"], "max_steps": source["max_steps"],
            "expected": {"pickup": p["pickup"], "ride_type": p["ride_type"], "destination": p["destination"],
                         "cab_type": p["selected_ride"], "payment_method": p["payment"],
                         "cancel_after_assignment": p["cancel_after_assignment"]}}
    for kind, value in (("app", app), ("topic", topic), ("task", task)):
        jsonschema.Draft202012Validator(read(f"schemas/{kind}.schema.json")).validate(value)
    policies, scoring = read("policies.json")["policies"], read("scoring.json")
    if len(policies) != 14 or {p["policy_id"] for p in policies} != set(POLICY_IDS):
        raise ValueError("Registry requires exactly 14 distinct policies")
    if scoring != {"schema_version": "1.0", "scoring_id": "ternary_14x5_v1",
                   "status_to_reward": {"PASS": 1, "INVALID": 0, "FAIL": -1},
                   "required_policy_count": 14, "required_verifier_count": 5,
                   "base_score": 0.5, "increment_per_pass": 0.1, "pass_threshold": 0.7,
                   "comparison": ">=", "all_invalid_reward": 0,
                   "aggregation": "any_fail_then_any_invalid_then_pass",
                   "episode_reward_frequency": "once_at_actor_stop", "progress_is_diagnostic": True}:
        raise ValueError("Scoring contract differs from the approved 14x5 / >=0.7 rule")
    from uber_clone_031.verification.checks import VERIFIERS
    for policy in policies:
        expected = {f'{policy["policy_id"]}.V{i}' for i in range(1, 6)}
        entries = policy["verifiers"]
        if len(entries) != 5 or {v["id"] for v in entries} != expected or len({v["implementation"] for v in entries}) != 5:
            raise ValueError("Each policy needs its five distinct expected verifier IDs and entry points")
        if any(v["implementation"] not in VERIFIERS or VERIFIERS[v["implementation"]][0] != v["id"] for v in entries):
            raise ValueError("Unknown or incorrectly bound verifier implementation")
    fingerprints = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.rglob("*.json"))}
    package = Path(__file__).parents[1]
    for path in sorted(package.rglob("*.py")):
        fingerprints["implementation/" + str(path.relative_to(package))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"app": app, "topic": topic, "task": task, "policies": policies, "scoring": scoring,
            "validity": read("generic/validity.json"), "interaction": read("generic/interaction.json"),
            "ui": read("apps/uber_clone/ui.json"), "state": read("apps/uber_clone/state.json"),
            "actions": read("apps/uber_clone/actions.json"), "fingerprints": fingerprints,
            "sha256": hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest(),
            "result_schema": read("schemas/result.schema.json")}
