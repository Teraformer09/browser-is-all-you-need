"""Verify a frozen policy-run receipt locally; never interact with Android or a model."""
import hashlib
import json
import sys
from pathlib import Path

# Direct script execution otherwise resolves an older installed wheel first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uber_clone_031.verification.evidence_readers import artifact_bytes
from uber_clone_031.verification.registry import load_registry
from uber_clone_031.verification.runner import verify_episode

reports = []
for directory in sys.argv[1:]:
    root = Path(directory)
    if not (root / "verifier_context.json").exists():
        raise ValueError("Legacy run: use its original verifier revision; do not overwrite it with new scoring.")
    context = json.loads((root / "verifier_context.json").read_text())
    registry = load_registry()
    if context["registry"]["sha256"] != registry["sha256"]:
        raise ValueError("Registry/implementation changed; restore the pinned verifier before replay.")
    context["registry"] = registry
    context["run_dir"] = str(root.resolve())
    for frame in context["frames"]:
        for kind in ("state", "ui", "screenshot"):
            if frame.get(kind): artifact_bytes(context, frame[kind])
    original = json.loads((root / "verdict.json").read_text())
    replay = verify_episode(context)
    if replay != original:
        raise ValueError("Frozen evidence does not reproduce the recorded verdict.")
    report = {"run_dir":str(root), "offline_replay_matches":True, "reward":replay["reward"],
              "status":replay["status"], "registry_sha256":registry["sha256"],
              "model_calls":0, "device_actions":0}
    (root / "evidence_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    reports.append(report)
print(json.dumps(reports))
