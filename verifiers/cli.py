from amazon_cart_001 import VERSION
from amazon_cart_001.harness.prompts import SYSTEM_PROMPT
from amazon_cart_001.harness.episode import Episode
from amazon_cart_001.agents.openrouter import model_info, call_model

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from amazon_cart_001.harness.evidence import save, digest


def export_episode(env, messages, calls, model, started, info):
    verdict = env.finalize()
    metadata = {"env_id":"terrano09/amazon-cart-001","task_id":env.task["task_id"],
        "runtime_version":VERSION,"model":model,"policy":"openrouter","model_calls":len(calls),
        "execution_location":"local-server-kvm","num_examples":1,"rollouts_per_example":1,
        "status":verdict["status"],"reward":verdict["reward"],"elapsed_seconds":round(time.monotonic()-started,2),
        "screenshot_count":sum("screen.png" in f["artifacts"] for f in env.frames),
        "actor_actions":len(env.transitions),"max_steps":env.task["max_steps"],"error":env.error,
        "completed_stages":verdict.get("progress",{}).get("completed_stages",0),"total_stages":6,
        "policy_count":14,"verifier_count":70,"model_pricing":info.get("pricing"),
        "training_eligible":verdict["training_eligible"],"no_action_repair":True}
    sample = {"example_id":0,"task":env.task["task_id"],"prompt":messages[:2],"completion":messages[2:],
              "reward":verdict["reward"],"correct":verdict["status"]=="PASS","num_steps":len(env.transitions),
              "rollout_number":0,"total_time":metadata["elapsed_seconds"],
              "info":{"scorecard":verdict,"run_metadata":metadata,"reward_timeline":env.history}}
    save(env.root/"metadata.json",metadata)
    save(env.root/"messages.json",messages)
    save(env.root/"model_calls.json",calls)
    save(env.root/"model_catalog.json",info)
    (env.root/"results.jsonl").write_text(json.dumps(sample)+"\n")
    files = {str(p.relative_to(env.root)):digest(p.read_bytes()) for p in sorted(env.root.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    save(env.root/"manifest.json",{"episode_id":env.episode,"files":files,"frames":env.frames})
    return metadata


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--confirm-eval",action="store_true")
    p.add_argument("--serial",required=True)
    p.add_argument("--adb",default=os.environ.get("ADB_PATH","adb"))
    p.add_argument("--apk",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--model",default="dots-studio/dots-3-note-preview:free")
    p.add_argument("--deadline-seconds",type=int,default=900)
    args = p.parse_args()
    if not args.confirm_eval:
        p.error("Explicit --confirm-eval authorization required")
    info = model_info(args.model)
    if not os.environ.get("OPENROUTER_API_KEY"):
        p.error("OPENROUTER_API_KEY is missing")
    started = time.monotonic()
    env = Episode(args.serial,args.apk,args.output_dir,args.adb)
    print("RUN_DIR="+str(env.root),flush=True)
    messages, calls = [], []
    try:
        env.reset()
        messages = [{"role":"system","content":SYSTEM_PROMPT},env.message()]
        save(env.root/"messages.json",messages)
        while not env.done and not env.error:
            if time.monotonic()-started > args.deadline_seconds:
                raise TimeoutError("Evaluation deadline exhausted")
            reply, receipt = call_model(args.model,messages)
            messages.append(reply); calls.append(receipt)
            save(env.root/"messages.json",messages); save(env.root/"model_calls.json",calls)
            env.step(reply["content"])
            messages.append(env.message())
            save(env.root/"messages.json",messages)
            point = env.history[-1]
            print(json.dumps({"step":len(env.transitions),"action":env.transitions[-1]["action"],
                "error":env.transitions[-1]["receipt"]["error"],"completed_stages":point["completed_stages"],
                "total_stages":6,"episode_reward":None,"policy_rewards":{r["policy_id"]:r["reward"] for r in point["policy_results"]}}),flush=True)
    except Exception as exc:
        env.error = type(exc).__name__+": "+str(exc)
        print("RUN_ERROR="+env.error,flush=True)
    metadata = export_episode(env,messages,calls,args.model,started,info)
    print(json.dumps({"run_dir":str(env.root),**metadata}),flush=True)
    return 2 if env.error else 0


if __name__ == "__main__":
    raise SystemExit(main())
