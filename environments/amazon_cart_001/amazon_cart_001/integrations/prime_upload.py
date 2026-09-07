"""Upload exactly one frozen cart model episode and verify every saved frame."""
import argparse
import base64
import json
import re
import time
from pathlib import Path
from amazon_cart_001.harness.evidence import digest, save

SECRET = re.compile(r"(?:pit_|ghp_|sk-or-v1-|sk-proj-)[A-Za-z0-9_-]{20,}")

def image_hashes(value):
    found=[]
    if isinstance(value,str):
        if value.startswith("data:image/png;base64,"):
            found.append(digest(base64.b64decode(value.split(",",1)[1])))
        elif value[:1] in ("[","{"):
            try:found.extend(image_hashes(json.loads(value)))
            except ValueError:pass
    elif isinstance(value,dict):
        if value.get("type")=="artifact" and value.get("media_type")=="image/png":
            found.append(Path(value["key"]).stem)
        else:
            for child in value.values():found.extend(image_hashes(child))
    elif isinstance(value,list):
        for child in value:found.extend(image_hashes(child))
    return found

def prepare(root):
    root=Path(root).resolve()
    if (root/"audit_disposition.json").exists():
        audit=json.loads((root/"audit_disposition.json").read_text())
        if audit.get("audit_status")=="INVALID":
            raise ValueError("This run was audited as harness-invalid; preserve it locally, not as a valid benchmark")
    metadata=json.loads((root/"metadata.json").read_text())
    if metadata.get("policy")!="openrouter" or metadata.get("model_calls",0)<1:
        raise ValueError("Only genuine model episodes can be uploaded as evaluations")
    if metadata.get("env_id")!="terrano09/amazon-cart-001":
        raise ValueError("Wrong environment identity")
    sample=json.loads((root/"results.jsonl").read_text())
    manifest=json.loads((root/"manifest.json").read_text())
    # Validate the entire frozen run before any remote write.
    for name,expected in manifest["files"].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes())!=expected:
            raise ValueError("Frozen artifact changed or escaped: "+name)
    frames=manifest["frames"]
    if len(frames)!=metadata["actor_actions"]+1:
        raise ValueError("Reset plus one frame per actor action is required")
    expected=[]
    images=[]
    for i,frame in enumerate(frames):
        ref=frame.get("artifacts",{}).get("screen.png")
        if not ref:
            raise ValueError("Missing screenshot for step "+str(i))
        path=(root/ref["path"]).resolve()
        if not path.is_relative_to(root/"frames"):
            raise ValueError("Screenshot path escaped")
        data=path.read_bytes()
        if digest(data)!=ref["sha256"] or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid screenshot")
        expected.append(ref["sha256"])
        # Include the same original PNG as an explicit per-step artifact.
        images.append({"step":i,"path":ref["path"],"sha256":ref["sha256"],
                       "data_url":"data:image/png;base64,"+base64.b64encode(data).decode()})
    logs={}
    allowed={"metadata.json","provenance.json","trajectory.jsonl","adb_actions.jsonl","verdict.json",
             "verifier_results.json","progress_history.json","initial_state.json","final_state.json",
             "installed_apk.json","model_calls.json","context.json","model_catalog.json"}
    for name in manifest["files"]:
        if name in allowed or name.startswith(("frames/","checkpoints/")) and name.endswith((".json",".xml")):
            logs[name]=(root/name).read_text()
    logs["manifest.json"]=(root/"manifest.json").read_text()
    sample["info"].update(saved_logs=logs,saved_log_sha256={k:digest(v.encode()) for k,v in logs.items()},
                          evidence_images=images)
    serialized=json.dumps(sample)
    if SECRET.search(serialized):
        raise ValueError("Credential-like value found; refusing upload")
    if len(serialized.encode())>25*1024*1024:
        raise ValueError("Full sample exceeds 25 MiB; no partial upload")
    return sample,metadata,expected

def verify_remote(remote,sample,expected):
    rows=remote.get("samples",[])
    if len(rows)!=1:raise ValueError("Expected exactly one remote sample")
    info=rows[0].get("info",{})
    if isinstance(info,str):info=json.loads(info)
    images=info.get("evidence_images",[])
    remote_logs=info.get("saved_logs",{})
    return {"screenshots_verified":len(images)==len(expected) and all(
                entry.get("step")==i and wanted in image_hashes(entry) for i,(entry,wanted) in enumerate(zip(images,expected))),
            "logs_verified":remote_logs==sample["info"]["saved_logs"],
            "reward_verified":rows[0].get("reward")==sample["reward"],
            "screenshot_count":len(expected),"saved_log_count":len(sample["info"]["saved_logs"])}

def upload(root,env_id):
    from prime_cli.core import APIClient, Config
    from prime_cli.utils.display import get_eval_viewer_url
    from prime_evals import EvalsClient
    root=Path(root)
    api=APIClient()
    identity=api.get("/user/whoami")["data"]
    if identity.get("slug")!="terrano09" or Config().team_id:
        raise ValueError("Upload requires terrano09 personal context")
    sample,metadata,expected=prepare(root)
    client=EvalsClient(api)
    receipt_path=root/"prime_upload.json"
    receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    metrics={"reward":sample["reward"],"success":int(sample["correct"]),"examples":1,
             "screenshots":len(expected),"completed_stages":metadata["completed_stages"],
             "total_stages":6,"policy_count":14,"verifier_count":70}
    for p in sample["info"]["scorecard"]["policies"]:
        metrics["policy_"+p["policy_id"]+"_reward"]=p["reward"]
        if p["policy_score"] is not None:metrics["policy_"+p["policy_id"]+"_support"]=p["policy_score"]
    if receipt and receipt.get("env_id")!=env_id:
        raise ValueError("Refusing to reuse a receipt for another environment")
    if not receipt.get("evaluation_id"):
        created=client.create_evaluation(name="amazon-cart-001-"+root.name,
            environments=[{"id":env_id}],model_name=metadata["model"],dataset="amazon_cart_001",
            framework="cart-14x5-v1",task_type="android-ui",
            description="One real OpenRouter model rollout on a local-server KVM emulator; 14 policies, 70 evidence strategies and original per-action screenshots. Not Prime-hosted compute. Offline simulated shopping only; no real purchase or checkout.",
            metadata=metadata,metrics=metrics,is_public=False)
        receipt={"evaluation_id":created["evaluation_id"],"env_id":env_id,"owner":"terrano09","created":created}
        save(receipt_path,receipt)
    eval_id=receipt["evaluation_id"]
    if not receipt.get("pushed"):
        response=client.push_samples(eval_id,[sample],max_payload_bytes=25*1024*1024,max_workers=1)
        receipt["push_response"]=response
        receipt["pushed"]=response.get("samples_pushed")==1 and response.get("samples_skipped")==0
        save(receipt_path,receipt)
        if not receipt["pushed"]:raise RuntimeError("Prime did not accept exactly one intact sample")
    if not receipt.get("finalized"):
        receipt["finalized"]=client.finalize_evaluation(eval_id,metrics=metrics)
        save(receipt_path,receipt)
    remote=client.get_samples(eval_id,limit=1)
    save(root/"prime_samples.json",remote)
    checked=verify_remote(remote,sample,expected)
    evaluation=client.get_evaluation(eval_id)
    receipt.update(url=get_eval_viewer_url(eval_id),verification=checked,evaluation=evaluation,
                   browser_rendering_verified=False)
    save(receipt_path,receipt)
    print(json.dumps({"evaluation_id":eval_id,"url":receipt["url"],**checked}),flush=True)
    if not all(checked[k] for k in ("screenshots_verified","logs_verified","reward_verified")):
        raise RuntimeError("Prime round-trip verification failed")
    return receipt

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--env-id",required=True)
    args=parser.parse_args()
    upload(args.run_dir,args.env_id)
