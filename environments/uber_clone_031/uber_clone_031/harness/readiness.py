"""Build/readiness checks only. Does not boot Android or request model inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from uber_clone_031.verification.registry import load_registry
from uber_clone_031.verification.runner import task_expectations
from uber_clone_031.cli import task_path
from uber_clone_031.harness.backend.task_specs import build_known_task, load_task_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, default=Path(os.environ.get("UBER031_APK_PATH", "/workspace/app/dummy_android_app/build/out/dummy-rl-app.apk")))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-kvm", action="store_true")
    args = parser.parse_args()
    registry = load_registry()
    task = build_known_task(load_task_spec(task_path()))
    tools = {name: shutil.which(name) for name in ("adb", "emulator", "java", "tesseract")}
    blockers = [name + " unavailable" for name, path in tools.items() if not path]
    if task_expectations(task) != registry["task"]["expected"]: blockers.append("YAML/JSON expectation mismatch")
    digest = hashlib.sha256(args.apk.read_bytes()).hexdigest() if args.apk.is_file() else None
    if digest is None: blockers.append("Compiled APK missing")
    kvm = os.access("/dev/kvm", os.R_OK | os.W_OK)
    if args.require_kvm and not kvm: blockers.append("KVM unavailable")
    versions = {}
    for name, command in (("adb", ["adb", "version"]), ("java", ["java", "-version"]), ("tesseract", ["tesseract", "--version"])):
        if tools[name]:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            versions[name] = (result.stdout or result.stderr).splitlines()[:2]
    report = {"setup_ready": not blockers, "evaluation_started": False, "model_calls": 0,
              "policy_count": len(registry["policies"]), "verifier_count": 70,
              "registry_sha256": registry["sha256"], "apk_sha256": digest,
              "tools": tools, "versions": versions, "kvm_accessible": kvm, "blockers": blockers,
              "evaluation_requires_explicit_approval": True,
              "live_probe_and_new_registry_end_to_end_validated": False,
              "remote_prime_version_updated": False}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if not blockers else 2


if __name__ == "__main__": raise SystemExit(main())
