"""Run the single bundled task through ADB and save a JSON report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from uber_clone_031.harness.backend.adb_device import AdbDevice
from uber_clone_031.harness.backend.task_specs import build_known_task, load_task_spec
from uber_clone_031.harness.backend.tasks.checks import get_check


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=str(Path(__file__).resolve().parents[1] / "task" / "uber_clone_031.yaml"))
    parser.add_argument("--output", default="artifacts/uber_clone_031/result.json")
    parser.add_argument("--serial", default=os.environ.get("ADB_SERIAL"))
    args = parser.parse_args()

    spec = load_task_spec(args.task)
    task = build_known_task(spec)
    if task is None:
        raise RuntimeError(f"unsupported task type: {spec.task_type}")
    device = AdbDevice(adb_path=os.environ.get("ADB_PATH", "adb"), package=spec.app.package, serial=args.serial)
    device.wait_for_ready()
    apk_path = Path(spec.app.apk_path or "")
    if apk_path.exists():
        device.install_apk(str(apk_path))
    raw = task.run_scripted(device)
    observation = {**raw, "exact_success": bool(raw.get("final_reward", 0.0) >= 1.0)}
    success = get_check(spec.success.check)(observation, spec.parameters) >= spec.success.threshold
    result = {
        "task_id": spec.task_id, "goal": spec.goal, "task_success": bool(success),
        "exact_success": bool(success), "reward": float(raw.get("reward", 0.0)),
        "final_reward": float(raw.get("final_reward", 0.0)), "reward_components": raw.get("reward_components", {}),
        "trajectory": raw.get("trajectory", []), "reset_metadata": raw.get("reset_metadata"),
        "device_serial": device.serial,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
