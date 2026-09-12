"""Explicitly authorized one-shot local model evaluation of the peach UI."""
import argparse
import json
import os
import time
from pathlib import Path
from amazon_cart_001.harness.peach_episode import PeachEpisode,SYSTEM_PROMPT
from amazon_cart_001.harness.recording import ScreenRecording
from amazon_cart_001.harness.evidence import save,digest
from amazon_cart_001.agents.openrouter import model_info,call_model
from amazon_cart_001.cli import export_episode

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--confirm-eval",action="store_true")
    p.add_argument("--serial",required=True)
    p.add_argument("--apk",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--ffmpeg",required=True)
    p.add_argument("--adb",default="adb")
    p.add_argument("--model",default="dots-studio/dots-3-note-preview:free")
    p.add_argument("--deadline-seconds",type=int,default=900)
    args=p.parse_args()
    if not args.confirm_eval: p.error("Explicit --confirm-eval required")
    if not os.environ.get("OPENROUTER_API_KEY"): p.error("OPENROUTER_API_KEY is unavailable")
    info=model_info(args.model)
    started=time.monotonic()
    env=PeachEpisode(args.serial,args.apk,args.output_dir,args.adb)
    print("RUN_DIR="+str(env.root),flush=True)
    messages,calls=[],[]
    recording=ScreenRecording(env.device,env.root,env.episode,args.ffmpeg)
    video=None
    try:
        env.reset()
        recording.start()
        messages=[{"role":"system","content":SYSTEM_PROMPT},env.message()]
        save(env.root/"messages.json",messages)
        while not env.done and not env.error:
            if time.monotonic()-started>args.deadline_seconds: raise TimeoutError("Episode deadline exhausted")
            if recording.errors: raise RuntimeError("Recording failed: "+str(recording.errors))
            reply,receipt=call_model(args.model,messages)
            messages.append(reply); calls.append(receipt)
            save(env.root/"messages.json",messages); save(env.root/"model_calls.json",calls)
            env.step(reply["content"])
            messages.append(env.message())
            point=env.history[-1]
            print(json.dumps({"step":len(env.transitions),"action":env.transitions[-1]["action"],
                "error":env.transitions[-1]["receipt"]["error"],"completed_stages":point["completed_stages"],
                "total_stages":6,"episode_reward":None,
                "policy_rewards":{v["policy_id"]:v["reward"] for v in point["policy_results"]}}),flush=True)
    except Exception as error:
        env.error=type(error).__name__+": "+str(error)
        print("RUN_ERROR="+env.error,flush=True)
    finally:
        try: video=recording.stop()
        except Exception as error:
            env.error=env.error or ("Video capture error: "+str(error))
    metadata=export_episode(env,messages,calls,args.model,started,info)
    metadata.update(app_variant="peach_sqlite_v1",package="com.primeintellect.amazonuidemo",
        installed_apk_sha256=env.context["installed_apk"].get("sha256"),
        implemented_verifier_slots=34,unavailable_verifier_slots=36,video=video,
        evaluator_note="Existing 14x5 rule; unimplemented visual/extra audit readers explicitly INVALID. Correlated state evidence is not independent.")
    save(env.root/"metadata.json",metadata)
    sample=json.loads((env.root/"results.jsonl").read_text())
    sample["info"]["run_metadata"]=metadata
    if video:
        video["actions"]= [{"step":t["step"],"start":t["started_monotonic"],"end":t["finished_monotonic"],
            "overlapping_segments":[s["index"] for s in video["segments"] if
                s["started_monotonic"]<=t["finished_monotonic"] and s["stopped_monotonic"]>=t["started_monotonic"]]}
            for t in env.transitions]
        save(env.root/"video"/"recording.json",video)
    (env.root/"results.jsonl").write_text(json.dumps(sample)+"\n")
    save(env.root/"manifest.json",{"episode_id":env.episode,"frames":env.frames,
        "files":{str(f.relative_to(env.root)):digest(f.read_bytes()) for f in sorted(env.root.rglob("*")) if f.is_file() and f.name!="manifest.json"}})
    print(json.dumps({"run_dir":str(env.root),**metadata}),flush=True)
    return 2 if env.error else 0

if __name__=="__main__": raise SystemExit(main())

