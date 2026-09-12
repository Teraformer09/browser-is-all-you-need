"""Publish frozen DemoCart UI evidence, explicitly as scripted and never as a model run."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

from amazon_cart_001.harness.evidence import save
from amazon_cart_001.verification.records import verify

OWNER = "terrano09"
ENV_NAME = "amazon-cart-001"
TASK_ID = "amazon_cart_001"
MODEL_LABEL = "scripted-ui-validation (no model)"
MAX_BYTES = 25 * 1024 * 1024
SECRET = re.compile(r"(?:pit_|ghp_|sk-or-v1-|sk-proj-)[A-Za-z0-9_-]{20,}")
TOP_LOGS = {
    "metadata.json", "installed_apk.json", "trajectory.jsonl", "adb_actions.jsonl",
    "progress_history.json", "initial_state.json", "final_state.json", "verdict.json",
}
FRAME_FILE = re.compile(
    r"frames/[0-9]{3}/(?:screen.png|ui.xml|runtime_before.json|runtime.json|"
    r"preferences.xml|journal.json|frame.json)$"
)
CHECKPOINT = re.compile(r"checkpoints/[0-9]{3}\.json$")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Artifact path escaped the run directory")
    return path


def read_json(path):
    return json.loads(path.read_text())


def prepare(root, task_file=None):
    """Read and validate everything before authentication or any remote write."""
    root = Path(root).resolve()
    task_file = Path(task_file or Path(__file__).parents[1] / "specs/task.json")
    meta = read_json(root / "metadata.json")
    if meta.get("task_id") != TASK_ID or meta.get("policy") != "scripted-ui-validation":
        raise ValueError("Expected the DemoCart scripted UI validation")
    if meta.get("model_calls") != 0 or meta.get("training_eligible") is not False:
        raise ValueError("This exporter cannot relabel a model/training episode")
    if meta.get("error") or meta.get("actor_actions") != 10 or meta.get("screenshots") != 11:
        raise ValueError("Expected the complete ten-action, eleven-frame DemoCart run")
    if (root / "audit_disposition.json").exists():
        if read_json(root / "audit_disposition.json").get("audit_status") == "INVALID":
            raise ValueError("Run has been audited as pipeline-invalid")
    manifest = read_json(root / "manifest.json")
    for name, expected in manifest["files"].items():
        if not (name in TOP_LOGS or FRAME_FILE.fullmatch(name) or CHECKPOINT.fullmatch(name)):
            raise ValueError("Artifact is outside the result-only allowlist: " + name)
        if digest(inside(root, name).read_bytes()) != expected:
            raise ValueError("Frozen artifact changed: " + name)
    if not TOP_LOGS.issubset(manifest["files"]):
        raise ValueError("Required run logs are missing")
    if digest(task_file.read_bytes()) != meta["task_sha256"]:
        raise ValueError("Task definition changed since the recorded run")
    task = read_json(task_file)
    verdict = read_json(root / "verdict.json")
    actual = verify(read_json(root / "final_state.json"), task, meta["episode_id"])
    if actual != verdict or meta.get("status") != verdict["status"] or meta.get("reward") != verdict["reward"]:
        raise ValueError("Recorded verdict does not match the original task and final state")
    transitions = [json.loads(line) for line in (root / "trajectory.jsonl").read_text().splitlines()]
    frames = manifest["frames"]
    history = read_json(root / "progress_history.json")
    if len(transitions) != 10 or len(frames) != 11 or len(history) != 11:
        raise ValueError("Action/frame/progress counts differ")
    for i, transition in enumerate(transitions, 1):
        if (transition.get("step") != i or transition.get("before") != i-1
                or transition.get("after") != i or transition.get("executed") is not True
                or transition.get("accepted") is not True):
            raise ValueError("Action receipt is incomplete or out of sequence")
        if history[i].get("action") != transition["action"]:
            raise ValueError("Progress does not match the recorded action")
    images = []
    for i, frame in enumerate(frames):
        if (frame.get("index") != i or frame.get("episode_id") != meta["episode_id"]
                or frame.get("stable") is not True or frame.get("errors")
                or history[i].get("step") != i):
            raise ValueError("Unstable, stale or out-of-order frame")
        ref = frame["artifacts"]["screen.png"]
        if ref["path"] != f"frames/{i:03d}/screen.png":
            raise ValueError("Screenshot is assigned to the wrong step")
        png = inside(root, ref["path"]).read_bytes()
        if (manifest["files"].get(ref["path"]) != ref["sha256"]
                or digest(png) != ref["sha256"] or not png.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("Original screenshot hash or format is invalid")
        images.append({"step": i, "path": ref["path"], "sha256": ref["sha256"],
                       "data_url": "data:image/png;base64," + base64.b64encode(png).decode()})

    def observation(i):
        state = frames[i]["state"]
        visible = {
            "step": i, "record_type": "recorded_scripted_ui_observation",
            "screen": state["screen"], "cart_items": state["cart_items"],
            "total_quantity": state["total_quantity"], "subtotal_paise": state["subtotal_paise"],
            "completed_stages": history[i]["completed_stages"], "total_stages": 6,
            "episode_status": history[i]["episode_status"],
            "episode_reward": history[i]["episode_reward"],
        }
        return {"role": "user", "content": [
            {"type": "text", "text": json.dumps(visible)},
            {"type": "image_url", "image_url": {"url": images[i]["data_url"]}},
        ]}

    # This is a dashboard presentation of recorded actions, NOT an original LLM conversation.
    prompt = [
        {"role": "system", "content": "Imported DemoCart SCRIPTED UI VALIDATION. No model was called. "
         "This conversation view reconstructs recorded actions and original screenshots; "
         "it is not an LLM prompt or generated rollout."},
        {"role": "user", "content": task["goal"]},
        observation(0),
    ]
    completion = []
    for i, transition in enumerate(transitions, 1):
        completion.append({"role": "assistant", "content": json.dumps({
            "actor": "scripted-ui-validation", "recorded_action": transition["action"],
            "executed": transition["executed"], "accepted": transition["accepted"],
        })})
        completion.append(observation(i))
    logs = {
        name: inside(root, name).read_text()
        for name in manifest["files"] if not name.endswith(".png")
    }
    logs["manifest.json"] = (root / "manifest.json").read_text()
    sample = {
        "example_id": 0, "task": TASK_ID, "answer": json.dumps(task["expected_items"]),
        "prompt": prompt, "completion": completion,
        "reward": verdict["reward"], "score": verdict["reward"],
        "correct": verdict["status"] == "PASS", "num_steps": len(transitions),
        "total_time": meta["elapsed_seconds"], "rollout_number": 0,
        "info": {
            "task_id": TASK_ID, "episode_id": meta["episode_id"], "source_run": root.name,
            "actor_type": "scripted-ui-validation", "model_calls": 0,
            "training_eligible": False, "is_hosted": False, "source_package_published": False,
            "transcript_type": "reconstructed_from_recorded_scripted_actions",
            "task_definition": task, "verdict": verdict, "progress_history": history,
            "evidence_images": [{k: v for k, v in image.items() if k != "data_url"} for image in images],
            "saved_logs": logs, "saved_log_sha256": {k: digest(v.encode()) for k, v in logs.items()},
            "original_manifest_file_count": len(manifest["files"]),
        },
    }
    serialized = json.dumps({"samples": [sample]}, ensure_ascii=True).encode()
    if SECRET.search(serialized.decode()):
        raise ValueError("Credential-like text found; refusing upload")
    if len(serialized) >= MAX_BYTES:
        raise ValueError("Complete result exceeds 25 MiB; no partial upload")
    summary = {
        "owner": OWNER, "environment": OWNER + "/" + ENV_NAME, "source_run": root.name,
        "actor_type": "scripted-ui-validation", "model_calls": 0, "training_eligible": False,
        "status": verdict["status"], "reward": verdict["reward"], "actions": 10,
        "screenshots": len(images), "saved_logs": len(logs), "payload_bytes": len(serialized),
        "payload_sha256": digest(serialized), "source_manifest_sha256": digest((root / "manifest.json").read_bytes()),
    }
    return sample, meta, summary


def image_hashes(value):
    if isinstance(value, str):
        if value.startswith("data:image/png;base64,"):
            return [digest(base64.b64decode(value.split(",", 1)[1], validate=True))]
        if value[:1] in ("[", "{"):
            try:
                return image_hashes(json.loads(value))
            except ValueError:
                pass
    elif isinstance(value, dict):
        if value.get("type") == "artifact" and value.get("media_type") == "image/png":
            return [Path(value["key"]).stem]
        return [h for child in value.values() for h in image_hashes(child)]
    elif isinstance(value, list):
        return [h for child in value for h in image_hashes(child)]
    return []


def verify_remote(remote, sample):
    rows = remote.get("samples", [])
    if len(rows) != 1:
        raise ValueError("Expected exactly one remote sample")
    row = rows[0]
    info = row.get("info", {})
    if isinstance(info, str):
        info = json.loads(info)
    expected = [item["sha256"] for item in sample["info"]["evidence_images"]]
    stored = image_hashes(row.get("prompt")) + image_hashes(row.get("completion"))
    return {
        "screenshots_verified": stored == expected,
        "screenshot_count": len(expected), "remote_screenshot_count": len(stored),
        "logs_verified": info.get("saved_logs") == sample["info"]["saved_logs"],
        "saved_log_count": len(sample["info"]["saved_logs"]),
        "reward_verified": row.get("reward") == sample["reward"],
        "scripted_label_verified": info.get("actor_type") == "scripted-ui-validation"
            and info.get("model_calls") == 0 and info.get("training_eligible") is False,
        "browser_rendering_verified": False,
    }


def upload(root, destination=None):
    from prime_cli.core import APIClient, Config
    from prime_cli.utils.display import get_eval_viewer_url
    from prime_evals import EvalsClient

    root = Path(root).resolve()
    sample, meta, summary = prepare(root)
    output = Path(destination or root.parents[1] / "prime_upload" / root.name).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError("Keep upload receipts outside the frozen source run")
    output.mkdir(parents=True, exist_ok=True)
    save(output / "prepared.json", summary)
    api = APIClient()
    if api.base_url.rstrip("/") != "https://api.primeintellect.ai":
        raise ValueError("Unexpected Prime API destination")
    if api.get("/user/whoami")["data"].get("slug") != OWNER or Config().team_id:
        raise ValueError("Requires terrano09 personal account")
    client = EvalsClient(api)
    receipt_path = output / "prime_upload.json"
    receipt = read_json(receipt_path) if receipt_path.exists() else {}
    if receipt and any(receipt.get(k) != summary[k] for k in ("owner", "source_run", "payload_sha256")):
        raise ValueError("Existing upload receipt belongs to different evidence")
    if not receipt:
        receipt = dict(summary)
        save(receipt_path, receipt)
    if not receipt.get("environment_id"):
        # Metadata-only registration: no wheel, APK, source archive or hosted compute.
        env = api.post("/environmentshub/resolve", json={
            "name": ENV_NAME, "visibility": "PRIVATE",
        })["data"]
        receipt.update(environment_id=env["id"], environment_registration=env)
        save(receipt_path, receipt)
    metrics = {
        "reward": sample["reward"], "success": int(sample["correct"]), "examples": 1,
        "screenshots": 11, "actor_actions": 10, "completed_stages": sample["info"]["verdict"]["completed_stages"],
        "total_stages": 6, "model_calls": 0, "scripted_ui_validation": 1,
    }
    if not receipt.get("evaluation_id"):
        created = client.create_evaluation(
            name="DemoCart-scripted-ui-validation-" + root.name,
            environments=[{"id": receipt["environment_id"]}], model_name=MODEL_LABEL,
            dataset=TASK_ID, framework="shopping-cart-v1-scripted", task_type="android-ui",
            description="Imported local SCRIPTED UI VALIDATION: 3 separate product searches, "
            "exactly 3 cart items, 10 UI actions, 11 original screenshots. ZERO model calls. "
            "Not a model benchmark and not Prime-hosted compute. Offline demo; no purchases.",
            tags=["scripted", "ui-validation", "no-model", "local-kvm"],
            metadata={**meta, "source_run": root.name, "evaluation_kind": "scripted-ui-validation",
                      "source_package_published": False, "is_hosted": False},
            metrics=metrics, is_public=False,
        )
        receipt.update(evaluation_id=created["evaluation_id"], created=created)
        save(receipt_path, receipt)
    eval_id = receipt["evaluation_id"]
    if not receipt.get("pushed"):
        # A previous process may have pushed a sample before saving its receipt.
        existing = client.get_samples(eval_id, limit=2)
        if existing.get("samples"):
            checks = verify_remote(existing, sample)
            if not all(checks[k] for k in ("screenshots_verified", "logs_verified", "reward_verified", "scripted_label_verified")):
                raise ValueError("Existing remote sample differs; refusing duplicate/overwrite")
            receipt["pushed"] = True
        else:
            pushed = client.push_samples(eval_id, [sample], max_payload_bytes=MAX_BYTES, max_workers=1)
            receipt["push_response"] = pushed
            receipt["pushed"] = pushed.get("samples_pushed") == 1 and pushed.get("samples_skipped") == 0
            if not receipt["pushed"]:
                save(receipt_path, receipt)
                raise RuntimeError("Prime did not accept exactly one complete sample")
        save(receipt_path, receipt)
    if not receipt.get("finalized"):
        receipt["finalized"] = client.finalize_evaluation(eval_id, metrics=metrics)
        save(receipt_path, receipt)
    remote = client.get_samples(eval_id, limit=2)
    save(output / "prime_samples.json", remote)
    checked = verify_remote(remote, sample)
    evaluation = client.get_evaluation(eval_id)
    receipt.update(url=get_eval_viewer_url(eval_id), verification=checked, evaluation=evaluation)
    save(receipt_path, receipt)
    print(json.dumps({"url": receipt["url"], "evaluation_id": eval_id,
                      "status": evaluation.get("status"), **checked}), flush=True)
    if not all(checked[k] for k in ("screenshots_verified", "logs_verified", "reward_verified", "scripted_label_verified")):
        raise RuntimeError("Uploaded result failed round-trip validation")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--upload", action="store_true", help="Authorize the results-only remote upload")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.upload:
        upload(args.run_dir, args.output_dir)
    else:
        print(json.dumps(prepare(args.run_dir)[2], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
