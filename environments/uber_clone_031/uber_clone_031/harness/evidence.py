"""Capture genuine ADB PNGs and synchronized state for every attempted action."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import struct
import subprocess
import zlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from uber_clone_031.verification.records import verify
from uber_clone_031.verification.registry import load_registry
from uber_clone_031.harness.ocr import capture_ocr
from uber_clone_031.verification.runner import task_expectations, verify_episode
from uber_clone_031.verification.progress import checkpoint_report, markdown_timeline


def validate_png(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("ADB did not return a PNG")
    offset, dimensions, has_pixels = 8, None, False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        payload = data[offset+8:offset+8+length]
        end = offset + 12 + length
        if end > len(data) or zlib.crc32(kind + payload) != struct.unpack(">I", data[end-4:end])[0]:
            raise ValueError("truncated PNG or checksum mismatch")
        if kind == b"IHDR":
            dimensions = struct.unpack(">II", payload[:8])
        if kind == b"IDAT":
            has_pixels = has_pixels or bool(payload)
        if kind == b"IEND":
            if not dimensions or min(dimensions) < 1 or not has_pixels:
                raise ValueError("PNG contains no image")
            return dimensions
        offset = end
    raise ValueError("PNG has no end marker")


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class EvidenceEnv:
    def __init__(self, env, root: str | Path, apk_path=None):
        self.env = env
        self.registry = load_registry()
        self.apk_path = Path(apk_path or os.environ.get("UBER031_APK_PATH") or Path(__file__).parents[2] / "app/dummy_android_app/build/out/dummy-rl-app.apk")
        self.verdict = None
        self.run_dir = Path(root) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
        self.run_dir.mkdir(parents=True, exist_ok=False)
        for name in ("screenshots", "states", "ui", "mutations", "probes", "ocr", "policies", "checkpoints"):
            (self.run_dir / name).mkdir()
        self.records = []
        self.progress_history = []
        self.invalid = False
        self.forbidden = False
        self.execution_errors = []
        self.last_observation = None
        self.trace_cursor = 0
        self.expected_apk_sha256 = hashlib.sha256(self.apk_path.read_bytes()).hexdigest() if self.apk_path.is_file() else None

    @property
    def task(self):
        return self.env.task

    def reset(self):
        obs = self.env.reset()
        if self.env.reset_failed:
            self.execution_errors.append(obs.get("reset_error", "reset failed"))
        try:
            self.installed_apk = self.env.device.installed_apk()
            write_json(self.run_dir / "installed_apk.json", self.installed_apk)
        except Exception as exc:
            self.installed_apk = None
            self.execution_errors.append(f"APK provenance: {type(exc).__name__}: {exc}")
        obs = self._record(obs, None, None)
        initial = self.records[0]
        missing = []
        for name, value in (("preferences", obs.get("prefs_xml")), ("UI", obs.get("ui_tree_xml")),
                            ("runtime probe", initial.get("runtime_probe")), ("mutation log", initial.get("mutations"))):
            if not value: missing.append(name)
        if not self.expected_apk_sha256 or not self.installed_apk or self.installed_apk.get("sha256") != self.expected_apk_sha256:
            missing.append("build-matched installed APK")
        if missing:
            self.env.reset_failed = True
            self.env.done = True
            obs["reset_error"] = "Preflight unavailable: " + ", ".join(missing)
        return obs

    def step(self, action):
        if hasattr(action, "to_dict"):
            action = action.to_dict()
        result = self.env.step(action)
        if result.info.get("action_valid") is False:
            self.invalid = True
        error = result.info.get("error")
        if error and any(x in str(error) for x in ("Timeout", "CalledProcessError", "Connection", "device offline")):
            self.execution_errors.append(str(error))
        if isinstance(action, dict) and action.get("type", action.get("action")) == "press_home":
            self.forbidden = True
        result.observation = self._record(result.observation, action, result.info)
        if result.done:
            self.finalize()
            result.observation = self.last_observation
        result.reward = result.observation["reward"]
        result.info.update(completed_stages=result.observation["scorecard"]["completed_stages"], total_stages=6,
                           task_success=result.observation["scorecard"]["task_success"],
                           evaluation_valid=result.observation["scorecard"]["evaluation_valid"])
        # Invalid finish is recoverable; only native success or budget terminates.
        result.done = result.done or self.env.steps >= self.task.max_steps
        return result

    def _record(self, obs, action, info):
        index = len(self.records)
        stem = f"{index:03d}"
        device = self.env.device
        device.phase = "evidence"
        errors = []
        try:
            prefs = obs.get("prefs_xml") or device.read_shared_prefs()
        except Exception as exc:
            prefs = ""
            errors.append(f"state capture: {type(exc).__name__}: {exc}")
        (self.run_dir / "states" / f"{stem}.xml").write_text(prefs)
        (self.run_dir / "ui" / f"{stem}.xml").write_text(obs.get("ui_tree_xml") or "")
        screenshot = None
        try:
            png = device.capture_png()
            width, height = validate_png(png)
            image_path = self.run_dir / "screenshots" / f"{stem}.png"
            image_path.write_bytes(png)
            screenshot = {"path": f"screenshots/{stem}.png", "sha256": hashlib.sha256(png).hexdigest(),
                          "bytes": len(png), "width": width, "height": height}
        except Exception as exc:
            errors.append(f"screenshot capture: {type(exc).__name__}: {exc}")
        probe, mutations, ocr = None, None, None
        try:
            probe = device.read_runtime_probe()
            write_json(self.run_dir / "probes" / f"{stem}.json", probe)
        except Exception as exc:
            errors.append(f"runtime probe: {type(exc).__name__}: {exc}")
        try:
            mutations = device.read_mutations()
            with (self.run_dir / "mutations" / f"{stem}.jsonl").open("w") as out:
                for event in mutations:
                    out.write(json.dumps(event) + "\n")
        except Exception as exc:
            errors.append(f"mutation capture: {type(exc).__name__}: {exc}")
        if screenshot and shutil.which("tesseract"):
            try:
                ocr = capture_ocr(self.run_dir / screenshot["path"], screenshot["sha256"], obs.get("ui_tree_xml") or "")
            except Exception as exc:
                ocr = {"error": f"{type(exc).__name__}: {exc}", "source_sha256": screenshot["sha256"]}
        else:
            ocr = {"error": "SCREENSHOT_OR_TESSERACT_UNAVAILABLE"}
        write_json(self.run_dir / "ocr" / f"{stem}.json", ocr)
        if obs.get("ui_error"):
            errors.append(obs["ui_error"])
        self.execution_errors = list(dict.fromkeys(self.execution_errors + errors + getattr(self.env, "execution_errors", [])))
        self.invalid |= self.env.invalid_action_seen
        self.forbidden |= self.env.forbidden_action_seen
        score = verify(self.task, prefs, steps=self.env.steps, invalid=self.invalid,
                       forbidden=self.forbidden, execution_errors=self.execution_errors,
                       evidence_ok=screenshot is not None and all(r["screenshot"] for r in self.records),
                       previous=self.records[-1]["scorecard"] if self.records else None,
                       action=self.env.last_action if action is not None else None, action_info=info)
        trace = getattr(device, "trace", [])
        adb_events = trace[self.trace_cursor:]
        self.trace_cursor = len(trace)
        with (self.run_dir / "adb_actions.jsonl").open("a") as out:
            for event in adb_events:
                out.write(json.dumps({"frame": index, **event}) + "\n")
        state_artifact = {"path": f"states/{stem}.xml", "sha256": hashlib.sha256(prefs.encode()).hexdigest()}
        ui_artifact = {"path": f"ui/{stem}.xml", "sha256": hashlib.sha256((obs.get("ui_tree_xml") or "").encode()).hexdigest()}
        record = {"index": index, "time": datetime.now(timezone.utc).isoformat(), "action": action,
                  "info": info, "is_action": info is not None and "runner_error" not in info,
                  "runtime_probe": probe, "mutations": mutations, "ocr": ocr,
                  "app_sequence": score["actual_state"].get("ride_action_sequence"), "adb_events": adb_events, "screenshot": screenshot, "state": state_artifact, "ui": ui_artifact, "scorecard": score,
                  "observation": obs, "errors": errors}
        self.records.append(record)
        interrupted = (info or {}).get("runner_error")
        context = self._verification_context(interrupted, "pipeline" if interrupted else "none")
        progress, snapshot = checkpoint_report(context, score,
            self.progress_history[-1] if self.progress_history else None)
        self.progress_history.append(progress)
        record["progress_report"] = progress
        write_json(self.run_dir / "checkpoints" / f"{stem}.json",
                   {"progress": progress, "verifier_snapshot": snapshot})
        self._write_progress()
        with (self.run_dir / "trajectory.jsonl").open("a") as out:
            out.write(json.dumps(record, sort_keys=True) + "\n")
        write_json(self.run_dir / "manifest.json", {"task_id": self.task.task_id, "episode_id": self.task.episode_id,
            "registry_sha256": self.registry["sha256"], "installed_apk": self.installed_apk, "frames": [
            {"index": r["index"], "screenshot": r["screenshot"], "state": r["state"], "ui": r["ui"], "action": r["action"]} for r in self.records]})
        write_json(self.run_dir / "scorecard.json", score)
        write_json(self.run_dir / "stage_history.json", [
            {"index": r["index"], "action": r["action"], "info": r["info"],
             "completed_stages": r["scorecard"]["completed_stages"], "total_stages": 6,
             "task_success": r["scorecard"]["task_success"], "stages": r["scorecard"]["stages"]}
            for r in self.records])
        obs = {**obs, "scorecard": score, "progress_fraction": score["progress_fraction"],
               "reward": 0.0, "final_reward": None, "episode_reward": None, "reward_pending": True,
               "reward_status": "PENDING", "progress_report": progress, "episode_verdict": None,
               "exact_success": False, "screenshot_path": str(self.run_dir / screenshot["path"]) if screenshot else None}
        self.last_observation = obs
        return obs

    def image_part(self):
        if not self.records or not self.records[-1]["screenshot"]:
            return None
        path = self.run_dir / self.records[-1]["screenshot"]["path"]
        return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()}}

    def _verification_context(self, stop_reason=None, failure_origin="none"):
        initial = self.records[0] if self.records else {}
        observation = initial.get("observation", {})
        capabilities = {"adb": bool(self.installed_apk), "preferences": bool(observation.get("prefs_xml")),
                        "ui_dump": bool(observation.get("ui_tree_xml")), "screenshot": bool(initial.get("screenshot")),
                        "mutation_log": bool(initial.get("mutations")), "runtime_probe": bool(initial.get("runtime_probe")),
                        "screenshot_ocr": bool(initial.get("ocr", {}).get("text"))}
        return {"registry": self.registry, "registry_valid": True, "frames": self.records,
                   "run_dir": str(self.run_dir), "task_id": self.task.task_id,
                   "task_expected": task_expectations(self.task), "max_steps": self.task.max_steps,
                   "episode_id": self.task.episode_id, "capabilities": capabilities,
                   "installed_apk": self.installed_apk, "expected_apk_sha256": self.expected_apk_sha256,
                   "capability_receipts": [e for e in initial.get("adb_events", [])
                                           if e.get("returncode") == 0 and e.get("phase") in {"setup", "observation", "evidence"}],
                   "stop_reason": stop_reason, "failure_origin": failure_origin}

    def _write_progress(self):
        write_json(self.run_dir / "progress_history.json", self.progress_history)
        (self.run_dir / "progress_report.md").write_text(markdown_timeline(self.progress_history))

    def finalize(self, stop_reason=None, failure_origin="none"):
        """One terminal policy verdict; stage fractions never become this reward."""
        if self.verdict is not None:
            return self.verdict
        context = self._verification_context(stop_reason, failure_origin)
        initial = self.records[0] if self.records else {}
        self.verdict = verify_episode(context)
        write_json(self.run_dir / "verdict.json", self.verdict)
        write_json(self.run_dir / "initial_state.json", initial.get("scorecard", {}).get("actual_state", {}))
        write_json(self.run_dir / "final_state.json", self.records[-1]["scorecard"]["actual_state"] if self.records else {})
        write_json(self.run_dir / "verifier_results.json", [r for p in self.verdict["policies"] for r in p["verifier_results"]])
        for policy in self.verdict["policies"]:
            write_json(self.run_dir / "policies" / (policy["policy_id"] + ".json"), policy)
        write_json(self.run_dir / "verifier_context.json", context)
        history = getattr(self, "progress_history", [])
        previous = history[-2] if len(history) > 1 else None
        progress, _ = checkpoint_report(context, self.last_observation.get("scorecard", {}),
                                        previous, final_verdict=self.verdict)
        if history and history[-1]["frame"] == progress["frame"]:
            history[-1] = progress
        else:
            history.append(progress)
        self.progress_history = history
        self._write_progress()
        self.last_observation = {**(self.last_observation or {}), "reward": self.verdict["reward"],
                                 "episode_reward": self.verdict["reward"], "reward_status": self.verdict["status"],
                                 "progress_report": progress,
                                 "final_reward": self.verdict["reward"], "reward_pending": False,
                                 "episode_verdict": self.verdict, "exact_success": self.verdict["status"] == "PASS"}
        return self.verdict

    def close(self):
        if hasattr(self.env, "close"):
            self.env.close()
