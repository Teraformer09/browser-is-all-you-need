"""Upload one frozen model run with every screenshot and allowlisted policy log."""
import argparse
import base64
import hashlib
import json
import re
import time
from pathlib import Path


def image_hashes(value):
    found = []
    if isinstance(value, str) and value.startswith("data:image/png;base64,"):
        found.append(hashlib.sha256(base64.b64decode(value.split(",", 1)[1])).hexdigest())
    elif isinstance(value, str) and value[:1] in ("[", "{"):
        try:
            found.extend(image_hashes(json.loads(value)))
        except (ValueError, TypeError):
            pass
    elif isinstance(value, dict) and value.get("type") == "artifact" and value.get("media_type") == "image/png":
        found.append(Path(value["key"]).stem)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(image_hashes(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(image_hashes(child))
    return found



def conversation_images(sample):
    """Map original PNG hashes to an image block already present in the trace."""
    found = {}
    for group in ("prompt", "completion"):
        for index, message in enumerate(sample.get(group, [])):
            content = message.get("content", [])
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (ValueError, TypeError):
                    continue
            if not isinstance(content, list):
                continue
            for block_index, block in enumerate(content):
                for digest in image_hashes(block):
                    found.setdefault(digest, f"/{group}/{index}/content/{block_index}")
    return found


def referenced_image(sample, pointer):
    """Resolve only a conversation image-block reference, never a file or URL."""
    if not isinstance(pointer, str) or not re.fullmatch(
            r"/(?:prompt|completion)/[0-9]+/content/[0-9]+", pointer):
        return None
    value = sample
    try:
        for part in pointer.split("/")[1:]:
            if isinstance(value, str):
                value = json.loads(value)
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value
    except (KeyError, IndexError, ValueError, TypeError):
        return None


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare_sample(root, max_payload_bytes=25 * 1024 * 1024):
    """Never export arbitrary host files, credentials, or incomplete screenshot sets."""
    if not isinstance(max_payload_bytes, int) or not 1 <= max_payload_bytes <= 64 * 1024 * 1024:
        raise ValueError("Upload size must be explicitly bounded to at most 64 MiB")
    root = root.resolve()
    sample = json.loads((root / "results.jsonl").read_text())
    metadata = json.loads((root / "metadata.json").read_text())
    if metadata["policy"] != "openrouter" or metadata.get("model_calls", 0) < 1:
        raise ValueError("Only genuine model evaluations belong in this upload workflow")
    frames = sample["info"]["manifest"]["frames"]
    if not frames or any(not frame.get("screenshot") for frame in frames):
        raise ValueError("Every captured step, including reset, must have a screenshot")
    images, expected = [], []
    existing_images = conversation_images(sample)
    for frame in frames:
        artifact = frame["screenshot"]
        path = (root / artifact["path"]).resolve()
        if not path.is_relative_to(root / "screenshots"):
            raise ValueError("Screenshot path escapes this run's screenshot directory")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != artifact["sha256"] or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Screenshot integrity check failed")
        expected.append(digest)
        entry = {"frame": frame["index"], "action": frame["action"],
                 "path": artifact["path"], "sha256": digest}
        if digest in existing_images:
            entry["message_ref"] = existing_images[digest]
        else:
            # Error-only frames may not occur in the model conversation.
            entry["data_url"] = "data:image/png;base64," + base64.b64encode(data).decode()
        images.append(entry)
    required = ("trajectory.jsonl", "adb_actions.jsonl", "stage_history.json", "verdict.json",
                "verifier_results.json", "verifier_context.json", "initial_state.json",
                "final_state.json", "installed_apk.json", "model_calls.json", "manifest.json")
    paths = [root / name for name in required]
    paths.extend(root / name for name in ("container.log", "execution_provenance.json", "evidence_validation.json", "progress_history.json", "progress_report.md")
                 if (root / name).is_file())
    for directory, pattern in (("states", "*.xml"), ("ui", "*.xml"), ("policies", "*.json"),
                               ("probes", "*.json"), ("mutations", "*.jsonl"), ("ocr", "*.json"), ("checkpoints", "*.json")):
        paths.extend(sorted((root / directory).glob(pattern)))
    logs = {}
    for path in paths:
        if not path.resolve().is_relative_to(root):
            raise ValueError("Evidence path escapes this run")
        logs[str(path.relative_to(root))] = path.read_text()
    secret_pattern = r"(?:pit_[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{24,}|sk-or-v1-[A-Za-z0-9]{24,})"
    if re.search(secret_pattern, json.dumps(sample) + json.dumps(logs)):
        raise ValueError("Credential-like content detected; refusing evidence upload")
    sample["info"]["saved_logs"] = logs
    sample["info"]["saved_log_sha256"] = {
        name: hashlib.sha256(value.encode()).hexdigest() for name, value in logs.items()}
    sample["info"]["evidence_images"] = images
    sample["num_steps"] = sum(frame.get("action") is not None for frame in frames)
    sample["total_time"] = metadata["elapsed_seconds"]
    sample["rollout_number"] = 0
    metadata["upload_schema"] = "android-adk-policy-evidence-v2"
    metadata["published_environment_updated"] = False
    metadata["local_runtime_version"] = metadata.get("runtime_version", "0.5.0")
    sample["info"]["run_metadata"] = metadata
    if len(json.dumps(sample).encode()) + 20 > max_payload_bytes:
        raise ValueError(f"Evidence exceeds the configured {max_payload_bytes} byte sample limit; no partial upload")
    return sample, metadata, expected


def verify_remote(remote, sample, expected):
    received = image_hashes(remote)
    samples = remote.get("samples", [])
    info = samples[0].get("info", {}) if len(samples) == 1 else {}
    if isinstance(info, str):
        info = json.loads(info)
    logs = info.get("saved_logs", {})
    logs_ok = all(logs.get(name) == value for name, value in sample["info"]["saved_logs"].items())
    images = info.get("evidence_images", [])
    frames_ok = len(images) == len(expected) and all(
        entry.get("frame") == frame["frame"] and digest in (
            image_hashes(entry) + image_hashes(referenced_image(samples[0], entry.get("message_ref"))))
        for entry, frame, digest in zip(images, sample["info"]["evidence_images"], expected))
    return {"remote_image_count": len(received),
            "screenshot_hashes_verified": not bool(set(expected) - set(received)),
            "screenshot_frames_verified": frames_ok, "saved_logs_verified": logs_ok,
            "saved_log_count": len(sample["info"]["saved_logs"])}


def main():
    from prime_cli.core import APIClient
    from prime_cli.utils.display import get_eval_viewer_url
    from prime_evals import EvalsClient

    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--env-id", default="an8yuvmg6kw539bkx9jk49b1")
    parser.add_argument("--max-payload-mib", type=int, choices=range(1, 65), default=25,
                        help="Explicit intact-sample cap; server limits may be lower (default: 25 MiB)")
    args = parser.parse_args()
    root = args.run_dir
    max_payload_bytes = args.max_payload_mib * 1024 * 1024
    sample, metadata, expected = prepare_sample(root, max_payload_bytes)
    metrics = {"reward": sample["reward"], "outcome_success": float(sample["info"]["scorecard"]["outcome_success"]),
        "safe_success": float(sample["correct"]), "screenshots": len(expected), "examples": 1,
        "completed_stages": metadata["completed_stages"], "total_stages": 6,
        "policies_passed": sum(p["status"] == "PASS" for p in sample["info"]["scorecard"]["policies"]),
        "policy_count": 14, "verifier_count": 70}
    for policy in sample["info"]["scorecard"]["policies"]:
        metrics["policy_" + policy["policy_id"] + "_reward"] = policy["reward"]
        if policy.get("policy_score") is not None:
            metrics["policy_" + policy["policy_id"] + "_support"] = policy["policy_score"]
    diagnostics = sample["info"]["scorecard"].get("stage_diagnostics", {})
    for name, stage in diagnostics.get("stages", {}).items():
        metrics["stage_" + name + "_completed"] = int(stage["completed"])
    metrics["progress_fraction"] = metadata["completed_stages"] / 6
    client = EvalsClient(APIClient())
    receipt_path = root / "prime_upload.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    if not receipt.get("evaluation_id"):
        created = client.create_evaluation(name="uber-clone-031-eval-" + root.name,
            environments=[{"id": args.env_id}], model_name=metadata["model"],
            dataset="uber_clone_031", framework="android-adk-policy-evidence-v2", task_type="android-ui",
            description=f"Local Docker/KVM model rollout, runtime {metadata['local_runtime_version']}: 14 policies, 70 verifiers, signed reward, stage progress, and screenshots for reset and every action. Not Prime-hosted compute.",
            metadata=metadata, metrics=metrics, is_public=False)
        receipt = {"evaluation_id": created["evaluation_id"], "created": created}
        save(receipt_path, receipt)
    eval_id = receipt["evaluation_id"]
    if receipt.get("pushed"):
        # Verify the original exported set, not files created locally after upload.
        names = receipt.get("exported_log_names")
        if names is None:
            previous = client.get_samples(eval_id, limit=1)["samples"][0]["info"]
            if isinstance(previous, str):
                previous = json.loads(previous)
            names = list(previous["saved_logs"])
        sample["info"]["saved_logs"] = {name: sample["info"]["saved_logs"][name] for name in names}
    receipt["exported_log_names"] = list(sample["info"]["saved_logs"])
    receipt["max_payload_bytes"] = max_payload_bytes
    save(receipt_path, receipt)
    if not receipt.get("pushed"):
        receipt["push_response"] = client.push_samples(eval_id, [sample], max_payload_bytes=max_payload_bytes, max_workers=1)
        if receipt["push_response"].get("samples_pushed") != 1 or receipt["push_response"].get("samples_skipped") != 0:
            save(receipt_path, receipt)
            raise RuntimeError("Prime did not accept exactly one complete sample")
        receipt["pushed"] = True
        save(receipt_path, receipt)
    if not receipt.get("finalized"):
        receipt["finalized"] = client.finalize_evaluation(eval_id, metrics=metrics)
        save(receipt_path, receipt)
    remote = client.get_samples(eval_id, limit=1)
    save(root / "prime_samples.json", remote)
    checked = verify_remote(remote, sample, expected)
    evaluation = client.get_evaluation(eval_id)
    for _ in range(18):
        if evaluation.get("status") not in ("PROCESSING", "PENDING", "RUNNING"):
            break
        time.sleep(10)
        evaluation = client.get_evaluation(eval_id)
    receipt.update(url=get_eval_viewer_url(eval_id), screenshot_count=len(expected), **checked,
        remote_sample_keys=list(remote) if isinstance(remote, dict) else [],
        verification_mode="Prime content-addressed artifact references match every local PNG; all allowlisted text logs match. Browser rendering not checked.",
        evaluation=evaluation)
    save(receipt_path, receipt)
    print(json.dumps({key: receipt[key] for key in ("evaluation_id", "url", "screenshot_count", *checked)}))
    if not all(checked[key] for key in ("screenshot_hashes_verified", "screenshot_frames_verified", "saved_logs_verified")):
        raise RuntimeError("Prime round-trip did not return every screenshot frame and log; inspect saved receipt")


if __name__ == "__main__":
    main()
