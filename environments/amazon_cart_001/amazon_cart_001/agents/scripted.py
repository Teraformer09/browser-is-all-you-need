"""Explicit scripted UI validation; no LLM, state writes, checkout or Prime upload."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from amazon_cart_001.harness.device import Device
from amazon_cart_001.harness.evidence import digest, save, nodes
from amazon_cart_001.verification.records import verify, result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--confirm-ui-run",action="store_true")
    p.add_argument("--serial",required=True)
    p.add_argument("--adb",default="adb")
    p.add_argument("--apk",required=True)
    p.add_argument("--output-dir",required=True)
    args=p.parse_args()
    if not args.confirm_ui_run:p.error("--confirm-ui-run authorizes a deterministic demo, not a model eval")
    task_file=Path(__file__).parents[1]/"specs/task.json"
    task=json.loads(task_file.read_text())
    root=Path(args.output_dir)/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid4().hex[:8])
    root.mkdir(parents=True,exist_ok=False)
    episode="cart_demo_"+uuid4().hex
    device=Device(args.serial,args.adb)
    plan=[]
    for item in task["expected_items"]:
        plan += [{"type":"type_text","element_id":"search_input","text":item["query"]},
                 {"type":"tap_element","element_id":"search_button"},
                 {"type":"tap_element","element_id":"add_"+item["sku"]}]
    plan.append({"type":"tap_element","element_id":"cart_button"})
    frames,transitions,history=[],[],[]
    error=None;started=time.monotonic()
    print("RUN_DIR="+str(root),flush=True)
    try:
        installed=device.installed(args.apk);save(root/"installed_apk.json",installed)
        device.start(episode)
        first=device.capture(root,0,episode);frames.append(first)
        if first["errors"]:raise RuntimeError("; ".join(first["errors"]))
        def checkpoint():
            score=verify(frames[-1].get("state"),task,episode)
            point={"step":len(transitions),"action":transitions[-1]["action"] if transitions else None,
                   "completed_stages":score["completed_stages"],"total_stages":6,"stages":score["stages"],
                   "episode_reward":None,"episode_status":"PENDING","screenshot":frames[-1]["artifacts"].get("screen.png")}
            history.append(point);save(root/"progress_history.json",history)
            save(root/"checkpoints"/f"{len(transitions):03d}.json",point)
        checkpoint()
        for action in plan:
            before=frames[-1]
            device.phase="action";start=len(device.trace)
            fresh=nodes(device.ui())
            target=next((n for n in fresh if n["id"]==action["element_id"]),None)
            if not target or not target["enabled"] or not (target["clickable"] or target["class"].endswith("EditText")):
                raise RuntimeError("Scripted target not currently interactable: "+action["element_id"])
            device.execute(action,target)
            end=len(device.trace)
            after=device.capture(root,len(frames),episode);frames.append(after)
            if after["errors"]:raise RuntimeError("; ".join(after["errors"]))
            new_events=after["state"]["events"][len(before["state"]["events"]):]
            if any(e["accepted"] is False for e in new_events):
                raise RuntimeError("App rejected scripted action: "+str(new_events[-1]))
            if action["type"]=="type_text":
                if after["state"]["draft_query"]!=action["text"]:raise RuntimeError("Search text did not update")
            else:
                expected_event="search" if action["element_id"]=="search_button" else "open_cart" if action["element_id"]=="cart_button" else "add_to_cart"
                if not any(e["action"]==expected_event for e in new_events):raise RuntimeError("Missing accepted app event")
            transitions.append({"step":len(transitions)+1,"action":action,"executed":True,"accepted":True,
                "trace_start":start,"trace_end":end,"before":before["index"],"after":after["index"],"app_events":new_events})
            (root/"trajectory.jsonl").write_text("".join(json.dumps(t)+"\n" for t in transitions))
            checkpoint()
            print(json.dumps({"step":len(transitions),"action":action,"completed_stages":history[-1]["completed_stages"],"total_stages":6}),flush=True)
    except Exception as exc:
        error=type(exc).__name__+": "+str(exc)
        print("RUN_ERROR="+error,flush=True)
    verdict=verify(frames[-1].get("state"),task,episode) if frames and not error else result("INVALID","UI_VALIDATION_PIPELINE_FAILED")
    if error:verdict["error"]=error
    if history:
        history[-1].update(episode_status=verdict["status"],episode_reward=verdict["reward"])
        save(root/"progress_history.json",history)
        save(root/"checkpoints"/f"{len(transitions):03d}.json",history[-1])
    save(root/"verdict.json",verdict)
    if frames:
        save(root/"initial_state.json",frames[0].get("state"))
        save(root/"final_state.json",frames[-1].get("state"))
    (root/"adb_actions.jsonl").write_text("".join(json.dumps(t)+"\n" for t in device.trace))
    meta={"task_id":task["task_id"],"episode_id":episode,"policy":"scripted-ui-validation","model_calls":0,
          "training_eligible":False,"actor_actions":len(transitions),"screenshots":sum("screen.png" in f["artifacts"] for f in frames),
          "elapsed_seconds":round(time.monotonic()-started,2),"error":error,"status":verdict["status"],"reward":verdict["reward"],
          "task_sha256":digest(task_file.read_bytes()),"implementation_sha256":{p.name:digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))}}
    save(root/"metadata.json",meta)
    save(root/"manifest.json",{"frames":frames,"files":{str(f.relative_to(root)):digest(f.read_bytes()) for f in sorted(root.rglob("*")) if f.is_file() and f.name!="manifest.json"}})
    print(json.dumps({"run_dir":str(root),**meta}),flush=True)
    return 0 if verdict["status"]=="PASS" else 2

if __name__=="__main__":raise SystemExit(main())
