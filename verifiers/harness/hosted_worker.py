"""Ordered file-mailbox worker inside a Prime Android VM; no public port.

Only reset/step/finalize are accepted. Credentials stay in the hosted controller.
Repeated delivery never repeats an already executed tap.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

from amazon_cart_001.harness.peach_episode import PeachEpisode
from amazon_cart_001.harness.recording import ScreenRecording
from amazon_cart_001.harness.emulator_config import runtime_options, emulator_command
from amazon_cart_001.harness.runtime_diagnostics import capture_failure
from amazon_cart_001.harness.startup_ui import prepare_startup_ui

RUNTIME = Path("/data/Tirtha/democart-runtime")
MAX_RESPONSE = 8 * 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024


def write_json(path, value):
    path = Path(path)
    staging = path.with_suffix(path.suffix + ".writing")
    staging.write_text(json.dumps(value, ensure_ascii=True))
    staging.replace(path)


def file_receipt(path):
    data = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check_root(value):
    root = Path(value).resolve()
    if root.parent != RUNTIME or re.fullmatch(r"[a-f0-9]{32}", root.name) is None:
        raise ValueError("Invalid private worker directory")
    return root


def validate_request(request, index):
    if not isinstance(request, dict) or type(request.get("sequence")) is not int or request["sequence"] != index:
        raise ValueError("Missing or out-of-order request sequence")
    operation = request.get("operation")
    keys = {"sequence", "operation", "action"} if operation == "step" else {"sequence", "operation"}
    if set(request) != keys or operation not in {"reset", "step", "finalize"}:
        raise ValueError("Unsupported worker request")
    if operation == "step" and (not isinstance(request["action"], str) or len(request["action"]) > 32768):
        raise ValueError("Action must be bounded model response text")


class Worker:
    def __init__(self, root, inspection=False, rubric_profile="legacy_v1", acceleration="kvm"):
        if rubric_profile not in {"legacy_v1", "peach_strict_v1"}:
            raise ValueError("Unknown rubric profile")
        self.rubric_profile = rubric_profile
        self.inspection = inspection is True
        self.options = runtime_options(acceleration)
        self.root, self.env, self.recorder, self.emulator = root, None, None, None
        self.finalized, self.recording_started = None, False

    def command(self, args, timeout=60):
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            with (self.root / "runtime.log").open("a") as stream:
                stream.write(json.dumps({"command": args, "returncode": None,
                    "timeout_seconds": timeout, "error": "COMMAND_TIMEOUT",
                    "stdout": decoded(exc.stdout), "stderr": decoded(exc.stderr)}) + "\n")
            raise
        with (self.root / "runtime.log").open("a") as stream:
            stream.write(json.dumps({"command": args, "returncode": result.returncode,
                                     "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        result.check_returncode()
        return result.stdout

    def boot(self):
        # No automatic fallback: software mode must be selected explicitly.
        write_json(self.root / "runtime-config.json", self.options)
        if self.options["requires_kvm"] and (not Path("/dev/kvm").is_char_device() or not os.access("/dev/kvm", os.R_OK | os.W_OK)):
            raise RuntimeError("KVM_UNAVAILABLE: Prime VM must expose usable /dev/kvm")
        sdk = Path(os.environ.get("ANDROID_SDK_ROOT", "/opt/android-sdk"))
        emulator = str(sdk / "emulator/emulator")
        if self.options["requires_kvm"]:
            self.command([emulator, "-accel-check"])
        self.command([emulator, "-version"])
        avd = self.root / "avd"
        avd.mkdir()
        os.environ["ANDROID_AVD_HOME"] = str(avd)
        os.environ["ANDROID_USER_HOME"] = str(self.root / "android-user")
        Path(os.environ["ANDROID_USER_HOME"]).mkdir()
        result = subprocess.run([str(sdk / "cmdline-tools/latest/bin/avdmanager"), "create", "avd",
            "--name", "democart", "--package", self.options["system_image"],
            "--path", str(avd / "democart.avd"), "--device", "pixel_6"],
            input="no\n", text=True, capture_output=True, timeout=60)
        (self.root / "avd-create.log").write_text(result.stdout + result.stderr)
        result.check_returncode()
        with (self.root / "emulator.log").open("wb") as log:
            command = emulator_command(emulator, self.options["acceleration"])
            write_json(self.root / "emulator-command.json", command)
            self.emulator = subprocess.Popen(command, stdout=log, stderr=log)
        deadline = time.monotonic() + self.options["boot_timeout_seconds"]
        while time.monotonic() < deadline:
            if self.emulator.poll() is not None:
                raise RuntimeError("EMULATOR_EXITED: see emulator.log")
            result = subprocess.run(["adb", "-s", "emulator-5556", "shell", "getprop", "sys.boot_completed"],
                                    capture_output=True, text=True, timeout=10)
            if result.stdout.strip() == "1":
                break
            time.sleep(2)
        else:
            raise RuntimeError("EMULATOR_BOOT_TIMEOUT")
        self.command(["adb", "-s", "emulator-5556", "shell", "input", "keyevent", "82"])
        self.install_apk()
        if self.options["startup_ui_timeout_seconds"]:
            prepare_startup_ui(self.root, self.command, self.options["startup_ui_timeout_seconds"],
                               initial_idle_seconds=self.options["startup_idle_seconds"],
                               recovery=self.options["system_ui_recovery"])
        self.env = PeachEpisode("emulator-5556", "/opt/democart/app.apk", self.root / "episodes",
                                execution_location="prime-vm-sandbox", rubric_profile=self.rubric_profile)
        self.env.reset()
        self.recorder = ScreenRecording(self.env.device, self.env.root, self.env.episode, "ffmpeg")
        self.recorder.start()
        self.recording_started = True
        write_json(self.root / "viewer_state.json", {"running": True, "inspection": self.inspection,
                                                   "episode_id": self.env.episode})

    def install_apk(self):
        wait = self.options["package_ready_timeout_seconds"]
        if wait:
            # Boot-complete does not mean PackageManager can answer yet on TCG.
            # Read-only probes have their own deadline; no task actions are retried.
            deadline = time.monotonic() + wait
            while True:
                try:
                    result = self.command(["adb", "-s", "emulator-5556", "shell",
                        "cmd", "package", "path", "android"], timeout=10)
                    if "package:" in result:
                        break
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("PACKAGE_MANAGER_READY_TIMEOUT")
                time.sleep(2)
        command = ["adb", "-s", "emulator-5556", "install"]
        if self.options["acceleration"] == "software":
            command.append("--no-streaming")
        self.command([*command, "-r", "/opt/democart/app.apk"],
                     timeout=self.options["install_timeout_seconds"])

    def observe(self):
        return {"message": self.env.message(), "done": self.env.done,
                "checkpoint": self.env.history[-1], "episode_id": self.env.episode}

    def handle(self, request):
        operation = request["operation"]
        if operation == "reset":
            if self.env is not None:
                raise RuntimeError("Worker already initialized")
            self.boot()
            return self.observe()
        if operation == "finalize":
            return self.finalize()
        if self.env is None:
            raise RuntimeError("Worker not initialized")
        self.env.step(request["action"])
        return self.observe()

    def finalize(self):
        if self.finalized is not None:
            return self.finalized
        errors, recording = [], None
        if self.recorder is not None and self.recording_started:
            try:
                recording = self.recorder.stop()
                if recording.get("errors") or not recording.get("playback"):
                    errors.append("RECORDING_INCOMPLETE")
            except Exception as exc:
                errors.append("RECORDING_EXPORT_FAILED: " + str(exc))
        if self.env is not None and self.inspection:
            self.env.done = True
            verdict = {"status": "NOT_SCORED", "reward": None, "training_eligible": False,
                       "kind": "manual_ui_inspection", "evaluation": False, "model_calls": 0}
        elif self.env is not None:
            verdict = self.env.finalize()
            if self.env.error:
                errors.append("EPISODE_PIPELINE_ERROR: " + self.env.error)
        else:
            verdict = {"status": "INVALID", "reward": 0, "training_eligible": False,
                       "reason_codes": ["EPISODE_NOT_STARTED"]}
        if errors:
            verdict = {**verdict, "task_verdict_before_capture_gate": dict(verdict),
                       "status": "INVALID", "reward": 0, "training_eligible": False, "reason_codes": errors}
        write_json(self.root / "viewer_state.json", {"running": False, "inspection": self.inspection})
        write_json(self.root / "hosted_verdict.json", verdict)
        if self.emulator is not None and self.emulator.poll() is None:
            self.emulator.terminate()
            try:
                self.emulator.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.emulator.kill()
                self.emulator.wait(timeout=10)
        archive = self.root / "evidence.zip"
        files = [p for p in self.root.glob("*.log") if p.is_file()]
        files.append(self.root / "hosted_verdict.json")
        files.extend(p for p in (self.root / "runtime-config.json", self.root / "emulator-command.json") if p.is_file())
        for diagnostic_dir in ("diagnostics", "startup"):
            files.extend(p for p in (self.root / diagnostic_dir).rglob("*") if p.is_file() and not p.is_symlink())
        if self.env is not None:
            files.extend(p for p in self.env.root.rglob("*") if p.is_file() and not p.is_symlink())
        if sum(p.stat().st_size for p in files) > MAX_ARCHIVE:
            raise RuntimeError("EVIDENCE_EXPORT_TOO_LARGE")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(files):
                output.write(path, str(path.relative_to(self.root)))
        self.finalized = {"verdict": verdict, "archive": file_receipt(archive),
                          "recording": recording, "episode_root": str(self.env.root) if self.env else None}
        return self.finalized


def serve(root, inspection=False, rubric_profile="legacy_v1", acceleration="kvm"):
    root.mkdir(parents=True, exist_ok=True)
    worker, index = Worker(root, inspection=inspection, rubric_profile=rubric_profile, acceleration=acceleration), 0
    options = runtime_options(acceleration)
    if acceleration == "software":
        # The clock starts at process start, so boot, package, install and the
        # startup gate all consume the same budget as the episode itself.
        budget = (options["boot_timeout_seconds"] + options["package_ready_timeout_seconds"] +
                  options["install_timeout_seconds"] + options["startup_ui_timeout_seconds"] +
                  options["episode_timeout_seconds"] + 30)
    else:
        budget = 1000
    deadline = time.monotonic() + budget
    try:
        while time.monotonic() < deadline:
            path = root / f"request-{index:03d}.json"
            if not path.exists():
                time.sleep(0.1)
                continue
            request = json.loads(path.read_text())
            try:
                validate_request(request, index)
                response = {"ok": True, "result": worker.handle(request)}
            except Exception as exc:
                response = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)}
                if worker.env:
                    worker.env.error = response["error"]
                try:
                    capture_failure(root, worker.env.device if worker.env else None)
                except Exception as diagnostic_error:
                    response["diagnostic_error"] = str(diagnostic_error)
            response["sequence"] = index
            write_json(root / f"response-{index:03d}.json", response)
            index += 1
            if request.get("operation") == "finalize":
                break
    finally:
        worker.finalize()


def exchange(root, index, acceleration="kvm", poll=False):
    staging, request = root / f"request-{index:03d}.incoming", root / f"request-{index:03d}.json"
    deadline = time.monotonic() + runtime_options(acceleration)["exchange_timeout_seconds"]
    if not request.exists():
        if not staging.exists():
            # Upload and exchange are separate RPCs; delivery can lag behind the
            # first poll. Awaiting delivery never stages or replays anything.
            if poll:
                print(json.dumps({"pending": True, "sequence": index, "delivery": "awaiting_upload"}))
                return
            while not staging.exists():
                if time.monotonic() > deadline:
                    raise TimeoutError("Request delivery deadline exceeded")
                time.sleep(0.2)
        validate_request(json.loads(staging.read_text()), index)
        staging.replace(request)
    elif staging.exists() and staging.read_bytes() != request.read_bytes():
        raise RuntimeError("Conflicting retry of a previously dispatched action")
    response = root / f"response-{index:03d}.json"
    if poll and not response.exists():
        print(json.dumps({"pending": True, "sequence": index}))
        return
    while not response.exists():
        if time.monotonic() > deadline:
            raise TimeoutError("Worker response deadline exceeded")
        time.sleep(0.1)
    if response.stat().st_size > MAX_RESPONSE:
        raise RuntimeError("Worker response too large")
    print(json.dumps(file_receipt(response)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["serve", "exchange"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--sequence", type=int, default=0)
    parser.add_argument("--inspection", action="store_true")
    parser.add_argument("--poll", action="store_true", help="Return pending immediately; never wait over RPC")
    parser.add_argument("--acceleration", choices=["kvm", "software"], default="kvm")
    parser.add_argument("--rubric-profile", choices=["legacy_v1", "peach_strict_v1"], default="legacy_v1")
    args = parser.parse_args()
    root = check_root(args.root)
    if not 0 <= args.sequence <= 20:
        parser.error("Sequence outside single-episode budget")
    serve(root, args.inspection, args.rubric_profile, args.acceleration) if args.operation == "serve" else exchange(root, args.sequence, args.acceleration, poll=args.poll)


if __name__ == "__main__":
    main()

