"""Real-device negative/recovery checks; no model calls and no hosted results."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from uber_clone_031.harness.backend.task_specs import build_known_task, load_task_spec
from uber_clone_031.harness.device import TracedAdbDevice
from uber_clone_031.harness.episode import RideStageEnv
from uber_clone_031.harness.evidence import EvidenceEnv, write_json
from uber_clone_031.cli import task_path


def tap(target): return {"type": "tap_element", "element_id": target}
def text(target, value): return {"type": "type_text", "element_id": target, "text": value}
BACK = {"type": "press_back"}
SWIPE = {"type": "swipe", "x1": 540, "y1": 1900, "x2": 540, "y2": 800, "duration_ms": 400}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    task = build_known_task(load_task_spec(task_path()))
    summary = []
    def env(name):
        return EvidenceEnv(RideStageEnv(task=task, device=TracedAdbDevice(adb_path=os.environ.get("ADB_PATH", "adb"),
                            serial=os.environ.get("ADB_SERIAL"), package=task.package)), args.output_dir / name)
    recovery = env("early_payment_finish_recovery")
    obs = recovery.reset()
    assert "payment_card" not in {n["id"] for n in obs["ui"]}
    original = obs["scorecard"]["actual_state"]
    for bad in (tap("payment_card"), {"type": "finish"}):
        result = recovery.step(bad)
        assert not result.done and not result.info["action_executed"]
        assert result.info["stage_transition_accepted"] is False
        assert result.observation["scorecard"]["actual_state"]["payment"] == original["payment"]
    actions = [text("pickup_input", "Airport Road"), BACK, tap("ride_type_premium"),
               text("drop_input", "City Centre"), BACK, tap("destination_search_button"),
               tap("ride_option_premium"), SWIPE, tap("payment_card"), tap("confirm_ride_button")]
    for action in actions:
        result = recovery.step(action)
        print(json.dumps({"case": "recovery", "step": recovery.env.steps,
                          "completed": result.observation["scorecard"]["completed_stages"], "info": result.info}), flush=True)
        assert not result.info["error"], result.info
    score = result.observation["scorecard"]
    assert result.done and score["safe_success"] and score["completed_stages"] == 6
    assert not score["process"]["no_invalid_action"]
    summary.append({"case": "early_payment_finish_recovery", "passed": True, "steps": recovery.env.steps,
                    "run_dir": str(recovery.run_dir), "scorecard": score})
    recovery.close()

    rejected = env("app_rejection_and_partial_recovery")
    rejected.reset()
    rejected.step(tap("ride_type_premium"))
    result = rejected.step(tap("destination_search_button"))
    assert result.info["action_executed"] and result.info["stage_transition_accepted"] is False
    assert "Enter a destination" in result.observation["last_error"]
    rejected.step(text("drop_input", "City Centre"))
    rejected.step(BACK)
    result = rejected.step(tap("destination_search_button"))
    assert result.info["stage_transition_accepted"] is True
    assert result.observation["scorecard"]["completed_stages"] == 2
    assert not result.done and result.reward == 2/6
    for malformed in ("[]", "null", {"type": []}):
        result = rejected.step(malformed)
        assert not result.info["schema_valid"] and not result.done
        assert result.observation["scorecard"]["completed_stages"] == 2
    summary.append({"case": "app_rejection_and_partial_recovery", "passed": True,
                    "run_dir": str(rejected.run_dir), "scorecard": result.observation["scorecard"]})
    rejected.close()
    write_json(args.output_dir / "live_validation.json", {"passed": True, "cases": summary, "model_calls": 0})
    print(json.dumps({"passed": True, "cases": len(summary), "model_calls": 0}), flush=True)


if __name__ == "__main__": main()
