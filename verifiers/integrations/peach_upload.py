"""Upload one frozen LOCAL peach-app episode, its original PNGs and actual MP4."""
import argparse
import base64
import json
from pathlib import Path
from amazon_cart_001.harness.evidence import digest,save
from amazon_cart_001.integrations.prime_account import api_client
from amazon_cart_001.integrations.prime_upload import prepare,verify_remote,SECRET

def video_hashes(value):
    if isinstance(value,str):
        if value.startswith("data:video/mp4;base64,"):
            return [digest(base64.b64decode(value.split(",",1)[1]))]
        if value[:1] in ("{","["):
            try: return video_hashes(json.loads(value))
            except ValueError: pass
    if isinstance(value,dict):
        if value.get("type")=="artifact" and value.get("media_type")=="video/mp4":
            return [Path(value["key"]).stem]
        return [h for child in value.values() for h in video_hashes(child)]
    if isinstance(value,list):
        return [h for child in value for h in video_hashes(child)]
    return []

def prepare_recorded(root):
    root=Path(root).resolve()
    sample,metadata,expected=prepare(root)
    if metadata.get("app_variant")!="peach_sqlite_v1":
        raise ValueError("Expected the new peach UI model episode")
    recording=json.loads((root/"video"/"recording.json").read_text())
    if recording.get("errors") or not recording.get("playback"):
        raise ValueError("A complete, decodable recording is required")
    ref=recording["playback"]
    path=(root/ref["path"]).resolve()
    if not path.is_relative_to(root/"video"): raise ValueError("Video path escaped")
    data=path.read_bytes()
    if digest(data)!=ref["sha256"] or b"ftyp" not in data[:40]: raise ValueError("Video integrity failure")
    sample["info"]["evidence_videos"]=[{"path":ref["path"],"sha256":ref["sha256"],
        "media_type":"video/mp4","source":"Android screenrecord","data_url":"data:video/mp4;base64,"+base64.b64encode(data).decode()}]
    logs=sample["info"]["saved_logs"]
    for name in ("video/recording.json","video/encode.log"):
        logs[name]=(root/name).read_text()
    sample["info"]["saved_log_sha256"]={k:digest(v.encode()) for k,v in logs.items()}
    payload=json.dumps(sample)
    if SECRET.search(payload): raise ValueError("Credential-like data: refusing upload")
    if len(payload.encode())>25*1024*1024: raise ValueError("Complete screenshot/video payload exceeds 25 MiB")
    return sample,metadata,expected,ref["sha256"],len(payload.encode())

def upload(root,env_id):
    from prime_evals import EvalsClient
    root=Path(root).resolve()
    sample,metadata,expected,video_sha,payload_bytes=prepare_recorded(root)
    api=api_client()
    client=EvalsClient(api)
    receipt_path=root/"prime_upload.json"
    receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    metrics={"reward":sample["reward"],"success":int(sample["correct"]),"examples":1,
        "screenshots":len(expected),"videos":1,"completed_stages":metadata["completed_stages"],
        "total_stages":6,"policy_count":14,"verifier_count":70,"implemented_verifier_slots":34}
    for policy in sample["info"]["scorecard"]["policies"]:
        metrics["policy_"+policy["policy_id"]+"_reward"]=policy["reward"]
    if receipt and receipt.get("env_id")!=env_id: raise ValueError("Receipt environment mismatch")
    if not receipt.get("evaluation_id"):
        created=client.create_evaluation(name="DemoCart-peach-model-recorded-"+root.name,
            environments=[{"id":env_id}],model_name=metadata["model"],dataset="amazon_cart_001-peach",
            framework="peach-sqlite-14x5-v1",task_type="android-ui",is_public=False,
            description="One real OpenRouter vision-model rollout on a LOCAL server KVM emulator, not Prime-hosted compute. Peach Java/XML/SQLite UI; original per-action PNGs and Android screenrecord MP4. Fourteen policies with five slots each; 34 implemented state/audit readers, 36 explicitly unavailable readers. Correlated channels are not independent. No real purchases.",
            metadata=metadata,metrics=metrics)
        receipt={"evaluation_id":created["evaluation_id"],"env_id":env_id,"owner":"terrano09","created":created,
            "execution_location":"local-server-kvm","payload_bytes":payload_bytes}
        save(receipt_path,receipt)
    evaluation_id=receipt["evaluation_id"]
    if not receipt.get("pushed"):
        response=client.push_samples(evaluation_id,[sample],max_payload_bytes=25*1024*1024,max_workers=1)
        receipt["push_response"]=response
        receipt["pushed"]=response.get("samples_pushed")==1 and response.get("samples_skipped")==0
        save(receipt_path,receipt)
        if not receipt["pushed"]: raise RuntimeError("Prime did not accept the complete sample")
    if not receipt.get("finalized"):
        receipt["finalized"]=client.finalize_evaluation(evaluation_id,metrics=metrics)
        save(receipt_path,receipt)
    remote=client.get_samples(evaluation_id,limit=1)
    save(root/"prime_samples.json",remote)
    verification=verify_remote(remote,sample,expected)
    info=remote["samples"][0].get("info",{})
    if isinstance(info,str): info=json.loads(info)
    verification["video_verified"]=video_sha in video_hashes(info.get("evidence_videos",[]))
    evaluation=client.get_evaluation(evaluation_id)
    receipt.update(url="https://app.primeintellect.ai/dashboard/evaluations/"+evaluation_id,
        verification=verification,evaluation=evaluation,browser_rendering_verified=False)
    save(receipt_path,receipt)
    print(json.dumps({"evaluation_id":evaluation_id,"url":receipt["url"],"status":evaluation["status"],**verification}),flush=True)
    if not all(verification[k] for k in ("screenshots_verified","logs_verified","reward_verified","video_verified")):
        raise RuntimeError("Incomplete Prime round-trip verification")
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("--env-id",default="ct6a6yjs0nvjkzexo3s57hqf")
    args=p.parse_args()
    upload(args.run_dir,args.env_id)

