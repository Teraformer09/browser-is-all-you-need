"""One fixed task, unrepaired actions, real screenshots, exportable Prime trace."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from uber_clone_031.harness.device import TracedAdbDevice
from uber_clone_031.harness.episode import RideStageEnv
from uber_clone_031.harness.backend.task_specs import build_known_task, load_task_spec

from uber_clone_031.harness.evidence import EvidenceEnv, write_json
from uber_clone_031.verification.records import RUBRIC_VERSION
from uber_clone_031.verification.registry import load_registry
from uber_clone_031.agents.openrouter import request_completion
from uber_clone_031.harness.actions import ACTION_SCHEMA, completion_payload

from uber_clone_031.harness.prompts import SYSTEM_PROMPT


def task_path():
    return Path(__file__).with_name("specs") / "task.json"


def public_observation(obs):
    # Never expose expected/actual prefs, legacy reward components, or scripted answers.
    result = {key: obs.get(key) for key in ("goal", "ui", "steps", "max_steps", "last_action", "last_error", "ui_error", "observation_freshness")}
    score = obs.get("scorecard") or {}
    result["progress"] = {"completed_stages": score.get("completed_stages", 0), "total_stages": 6,
                          "task_success": score.get("task_success", False),
                          "episode_reward_status": obs.get("reward_status", "PENDING"),
                          "stages": {key: {"status": value["status"], "completed": value["completed"]}
                                     for key, value in score.get("stages", {}).items()}}
    return result


def observation_message(env, obs):
    content = [{"type": "text", "text": json.dumps(public_observation(obs), sort_keys=True)}]
    picture = env.image_part()
    if picture:
        content.append(picture)
    return {"role": "user", "content": content}


from uber_clone_031.agents.openrouter import model_action


def parse_action(content):
    # Syntax handling only, no task-specific target/value substitution or oracle fallback.
    text = content.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-eval", action="store_true", help="Explicit authorization to start a device/model rollout")
    parser.add_argument("--policy", choices=("scripted", "openrouter"), required=True)
    parser.add_argument("--model", default="minimax/minimax-m3:free")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--deadline-seconds", type=int, default=600)
    parser.add_argument("--response-format", choices=("text", "json_object", "json_schema"), default="text")
    args = parser.parse_args()
    if not args.confirm_eval:
        parser.error("Evaluation is disabled until explicitly approved; pass --confirm-eval only after approval.")
    load_registry()
    task = build_known_task(load_task_spec(task_path()))
    device = TracedAdbDevice(adb_path=os.environ.get("ADB_PATH", "adb"),
        serial=os.environ.get("ADB_SERIAL"), package=task.package)
    env = EvidenceEnv(RideStageEnv(task=task, device=device, max_steps=task.max_steps), args.output_dir)
    print("RUN_DIR=" + str(env.run_dir), flush=True)
    started = time.monotonic()
    messages, usage, failure = [], [], None
    obs = env.reset()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, observation_message(env, obs)]
    prompt_count = len(messages)
    oracle = []
    if args.policy == "scripted":
        for action in task.action_sequence():
            oracle.append(action.to_dict() if hasattr(action, "to_dict") else action)
            item = oracle[-1]
            if item.get("action", item.get("type")) in {"input_resource", "type_text"}:
                oracle.append({"type": "press_back"})
            if item.get("target", item.get("element_id")) == "ride_option_premium":
                oracle.append({"type": "swipe", "x1":540, "y1":1900, "x2":540, "y2":800, "duration_ms":400})
    try:
        if env.env.reset_failed:
            raise RuntimeError("Android reset failed")
        for step in range(task.max_steps):
            if time.monotonic() - started > args.deadline_seconds:
                raise TimeoutError("Evaluation wall-clock budget exhausted")
            if args.policy == "scripted":
                if step >= len(oracle):
                    break
                action = oracle[step]
                reply = {"role": "assistant", "content": json.dumps(action)}
            else:
                reply, receipt = model_action(args.model, messages, args.response_format)
                usage.append(receipt)
                action = parse_action(reply["content"])
            messages.append(reply)
            result = env.step(action)
            obs = result.observation
            messages.append(observation_message(env, obs))
            write_json(env.run_dir / "messages.json", messages)
            write_json(env.run_dir / "model_calls.json", usage)
            print(json.dumps({"step": step+1, "action": action, "reward":obs.get("episode_reward"),
                              "reward_status":obs.get("reward_status", "PENDING"),
                              "policy_rewards":{k:v["reward"] for k,v in obs["progress_report"]["policies"].items()},
                              "newly_completed_stages":obs["progress_report"]["newly_completed_stages"],
                              "completed_stages":obs["scorecard"]["completed_stages"], "total_stages":6,
                              "task_success":obs["scorecard"]["task_success"], "done":result.done, "error":result.info.get("error")}), flush=True)
            if result.done:
                break
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        env.execution_errors.append(failure)
        obs = env._record(obs, None, {"runner_error": failure})
        print("RUN_ERROR=" + failure, flush=True)
    verdict = env.finalize(stop_reason=failure, failure_origin="pipeline" if failure else "none")
    obs = env.last_observation
    stages = obs["scorecard"]
    score = {**verdict, "stage_diagnostics": stages, "outcome_success": stages["task_success"],
             "safe_success": verdict["status"] == "PASS"}
    model_name = args.model if args.policy == "openrouter" else "scripted-oracle-validation"
    metadata = {"env_id":"terrano09/uber-clone-031", "task_id":task.task_id,
        "runtime_version":"0.7.0", "model_response_format":args.response_format,
        "action_schema_sha256":hashlib.sha256(json.dumps(ACTION_SCHEMA, sort_keys=True).encode()).hexdigest() if args.response_format == "json_schema" else None, "reward_reporting_version":"checkpoint-policies-v1",
        "model":model_name, "policy":args.policy, "rubric_version":env.registry["scoring"]["scoring_id"],
        "stage_rubric_version":RUBRIC_VERSION,
        "execution_location":"local-docker-kvm", "installed_apk":env.installed_apk, "registry_sha256":env.registry["sha256"],
        "scoring_id":"ternary_14x5_v1", "policy_count":14, "verifier_count":70,
        "status":verdict["status"], "training_eligible":verdict["training_eligible"], "num_examples":1, "rollouts_per_example":1,
        "max_steps":task.max_steps, "seed":task.seed, "no_action_repair":True,
        "task_sha256":hashlib.sha256(task_path().read_bytes()).hexdigest(),
        "verifier_sha256":load_registry()["sha256"],
        "elapsed_seconds":round(time.monotonic()-started, 2), "model_calls":len(usage),
        "screenshot_count":sum(bool(r["screenshot"]) for r in env.records), "error":failure,
        "completed_stages":stages["completed_stages"], "total_stages":6, "evaluation_valid":verdict["status"] != "INVALID"}
    manifest = json.loads((env.run_dir / "manifest.json").read_text())
    sample = {"example_id":0, "task":task.task_id, "prompt":messages[:prompt_count],
        "completion":messages[prompt_count:], "reward":score["reward"],
        "correct":score["safe_success"], "info":{"scorecard":score, "run_metadata":metadata,
        "manifest":manifest, "model_calls":usage, "reward_timeline":env.progress_history}}
    write_json(env.run_dir / "metadata.json", metadata)
    write_json(env.run_dir / "result.json", {**metadata, "scorecard":score, "verdict":verdict})
    write_json(env.run_dir / "scorecard.json", score)
    write_json(env.run_dir / "messages.json", messages)
    write_json(env.run_dir / "model_calls.json", usage)
    (env.run_dir / "results.jsonl").write_text(json.dumps(sample) + "\n")
    print(json.dumps({"run_dir":str(env.run_dir), "reward":score["reward"],
        "outcome_success":score["outcome_success"], "screenshots":metadata["screenshot_count"]}), flush=True)
    env.close()
    return 2 if failure or (args.policy == "scripted" and not score["safe_success"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
