"""Observer-only checkpoint policy rewards; never a replacement training reward."""
from uber_clone_031.verification.runner import verify_episode

TASK_STAGES = {"T1": "pickup", "T2": "ride_type", "T3": "destination",
               "T4": "cab", "T5": "payment", "T6": "booking"}


def checkpoint_report(context, stages, previous=None, final_verdict=None):
    """Run unchanged predicates on the prefix; distinguish not-yet-due from INVALID.

    A checkpoint PASS is revocable: a later field edit or policy violation can
    change it. Pending display rows retain the raw votes in checkpoint evidence,
    but never turn an unfinished episode into an agent failure or a training score.
    """
    snapshot = final_verdict if final_verdict is not None else verify_episode(context)
    terminal = final_verdict is not None
    if not terminal:
        snapshot = {**snapshot, "assessment_point": "checkpoint", "checkpoint_only": True,
                    "training_eligible": False}
    stage_values = stages.get("stages", {})
    completed = [name for name, value in stage_values.items() if value["completed"]]
    old = set((previous or {}).get("completed_stage_ids", []))
    has_actions = any(frame.get("is_action") for frame in context.get("frames", []))
    policies = {}
    for result in snapshot["policies"]:
        pid = result["policy_id"]
        status, reward = result["status"], result["reward"]
        if not terminal:
            stage = stage_values.get(TASK_STAGES.get(pid), {})
            not_due = pid in TASK_STAGES and status != "PASS" and not stage.get("ever_completed") and \
                stage.get("status") not in {"mismatch", "rejected", "invalidated"} and \
                context.get("failure_origin", "none") == "none"
            if not_due or (pid not in {"V1", "V2", *TASK_STAGES} and not has_actions):
                status, reward = "PENDING", None
        policies[pid] = {"status": status, "reward": reward, "support_score": result["policy_score"],
                         "passed_verifiers": result["passed_verifiers"],
                         "failed_verifiers": result["failed_verifiers"],
                         "invalid_verifiers": result["invalid_verifiers"],
                         "provisional": not terminal}
    report = {"frame": len(context.get("frames", [])) - 1,
              "assessment": "episode_final" if terminal else "checkpoint",
              "episode_status": snapshot["status"] if terminal else "PENDING",
              "episode_reward": snapshot["reward"] if terminal else None,
              "training_reward_available": terminal,
              "completed_stages": stages.get("completed_stages", 0), "total_stages": 6,
              "progress_fraction": stages.get("progress_fraction", 0),
              "completed_stage_ids": completed,
              "newly_completed_stages": [name for name in completed if name not in old],
              "invalidated_stages": sorted(old - set(completed)),
              "policies": policies, "policy_count": 14, "verifier_count": 70,
              "policy_pass_count": sum(p["status"] == "PASS" for p in policies.values()),
              "cumulative_reward": False}
    return report, snapshot


def markdown_timeline(history):
    lines = ["# Step-by-step reward report", "",
             "Policy rewards below are checkpoint results, not accumulated episode rewards. "
             "PENDING means no terminal reward yet; it does not mean INVALID. "
             "Earlier policy PASS results can be invalidated by later actions.", "",
             "| Frame | Completed task stages | Newly completed | Policy PASS count | Episode reward | Policy rewards |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in history:
        rewards = ", ".join(f"{pid}={p['reward']:+d}" if p["reward"] is not None else f"{pid}=PENDING"
                            for pid, p in row["policies"].items())
        reward = row["episode_reward"] if row["training_reward_available"] else "PENDING"
        lines.append(f"| {row['frame']} | {row['completed_stages']}/6 | "
                     f"{', '.join(row['newly_completed_stages']) or '—'} | "
                     f"{row['policy_pass_count']}/14 | {reward} | {rewards} |")
    return "\n".join(lines) + "\n"
