"""Report all fixed-task attempts; no outcome-based stopping or reweighting."""
import argparse
import json
import re
from math import comb, sqrt
from pathlib import Path


def estimate(n, c, k=3):
    if any(type(v) is not int for v in (n, c, k)) or not (1 <= k <= n and 0 <= c <= n):
        raise ValueError("Require integer 1 <= k <= n and 0 <= c <= n")
    return 1.0 - (comb(n - c, k) if n - c >= k else 0) / comb(n, k)


def wilson(c, n):
    if not n:
        return None
    z = 1.959963984540054
    p, divisor = c / n, 1 + z * z / n
    center = (p + z * z / (2 * n)) / divisor
    radius = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / divisor
    return [max(0.0, center - radius), min(1.0, center + radius)]


def summarize(attempts, planned=12, k=3, target=(0.7, 0.9)):
    if type(planned) is not int or type(k) is not int or k < 1 or planned < k:
        raise ValueError("Invalid fixed attempt budget")
    if not isinstance(attempts, list) or len(attempts) > planned:
        raise ValueError("Too many or malformed attempts")
    if (not isinstance(target, (tuple, list)) or len(target) != 2 or
            any(type(v) not in (int, float) for v in target) or not 0 <= target[0] <= target[1] <= 1):
        raise ValueError("Invalid target band")
    ids, episodes, contracts, models = set(), set(), set(), set()
    counts = {"PASS": 0, "FAIL": 0, "INVALID": 0}
    for a in attempts:
        if not isinstance(a, dict):
            raise ValueError("Each attempt must be an object")
        for field in ("attempt_id", "model", "rubric_sha256", "task_sha256", "actor_config_sha256", "campaign_sha256"):
            if not isinstance(a.get(field), str) or not a[field]:
                raise ValueError("Missing attempt identity/configuration: " + field)
        for field in ("rubric_sha256", "task_sha256", "actor_config_sha256", "campaign_sha256"):
            if re.fullmatch(r"[a-f0-9]{64}", a[field]) is None:
                raise ValueError("Invalid configuration hash: " + field)
        episode = a.get("episode_id")
        if episode is None:
            if a.get("status") != "INVALID" or a.get("phase") != "setup" or not a.get("reason_codes"):
                raise ValueError("Only documented setup-invalid attempts may lack an Android episode")
        elif not isinstance(episode, str) or re.fullmatch(r"peach_[a-f0-9]{32}", episode) is None:
            raise ValueError("Invalid Android episode identity")
        if a["attempt_id"] in ids or (episode is not None and episode in episodes):
            raise ValueError("Duplicate attempt or episode; cannot count a replay twice")
        if a.get("status") not in counts or type(a.get("reward")) not in (int, float) or a["reward"] != {"PASS": 1, "FAIL": -1, "INVALID": 0}[a["status"]]:
            raise ValueError("Inconsistent verdict")
        ids.add(a["attempt_id"])
        if episode is not None:
            episodes.add(episode)
        contracts.add(tuple(a[f] for f in ("rubric_sha256", "task_sha256", "actor_config_sha256", "campaign_sha256")))
        models.add(a["model"])
        counts[a["status"]] += 1
    if len(contracts) > 1 or len(models) > 1:
        raise ValueError("Do not pool different rubrics/tasks/models/sampling settings/campaigns into this fixed-task estimate")
    n, c = counts["PASS"] + counts["FAIL"], counts["PASS"]
    complete = len(attempts) == planned
    conditional = estimate(n, c, k) if n >= k else None
    primary = conditional if complete and counts["INVALID"] == 0 else None
    interval = wilson(c, n)
    return {"planned_attempts": planned, "recorded_attempts": len(attempts), "valid_attempts": n,
            "counts": counts, "complete": complete, "k": k,
            "pass_at_k": primary, "pass_at_k_conditional_on_valid": conditional,
            "operational_pass_at_k_invalid_as_non_success": estimate(len(attempts), c, k) if complete else None,
            "pass_at_1_valid": c / n if n else None,
            "pass_at_1_wilson_95": interval,
            "pass_at_k_iid_plugin_interval_95": [1 - (1 - p) ** k for p in interval] if interval else None,
            "interval_note": "Wilson interval transformed under an IID Bernoulli assumption; not a direct confidence interval for the finite-sample estimator, nor proof of general task competence.",
            "target_band": list(target),
            "target_met": target[0] <= primary <= target[1] if primary is not None else None,
            "target_assessment": "MEASURED" if primary is not None else "INCOMPLETE_OR_INVALID_ATTEMPTS",
            "estimator": "1-C(n-c,k)/C(n,k)", "attempts": attempts,
            "inference_scope": "One fixed DemoCart task and frozen actor settings, not a multi-task benchmark."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("attempts_json", help="JSON list of all attempt verdicts and pinned identities")
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(Path(args.attempts_json).read_text())), indent=2))


if __name__ == "__main__":
    main()

