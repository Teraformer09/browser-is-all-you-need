"""One bounded Prime VM per rollout, with verified export before teardown."""
import base64
import hashlib
import json
import re
import shlex
import time
from pathlib import Path, PurePosixPath
from uuid import uuid4
from zipfile import ZipFile

from amazon_cart_001.harness.hosted_worker import MAX_ARCHIVE, MAX_RESPONSE, RUNTIME
from amazon_cart_001.harness.emulator_config import runtime_options

DEFAULT_IMAGE = "prime/devjangid-wootzapp/democart-peach:0.5.1"
MODULE = "amazon_cart_001.harness.hosted_worker"
MAX_DASHBOARD_BYTES = 25 * 1024 * 1024


def sdk_client(cache):
    from prime_sandboxes import SandboxClient
    from prime_sandboxes.core import APIClient
    client = APIClient()
    # SDK auth cache belongs to this run, not ~/.prime on a shared server.
    cache.mkdir(parents=True, exist_ok=True)
    client.config.config_dir = cache
    return SandboxClient(client)


def invalid(reason):
    return {"status": "INVALID", "reward": 0, "training_eligible": False,
            "reason_codes": [reason]}


def archive_payload(path):
    """Inspect, don't extract, a bounded archive. Include actual media and receipts."""
    data = path.read_bytes()
    if len(data) > MAX_ARCHIVE:
        raise ValueError("Evidence archive exceeds transfer limit")
    payload = {"evidence_archive": {"path": "evidence.zip", "sha256": hashlib.sha256(data).hexdigest(),
               "media_type": "application/zip", "data_url": "data:application/zip;base64," + base64.b64encode(data).decode()},
               "evidence_videos": [], "saved_logs": {}}
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(entry.file_size for entry in entries) > MAX_ARCHIVE:
            raise ValueError("Evidence archive expansion exceeds limit")
        names = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or entry.filename in names:
                raise ValueError("Unsafe or duplicate evidence archive entry")
            names.add(entry.filename)
            if name.name == "screen-recording.mp4":
                media = archive.read(entry)
                if b"ftyp" not in media[:40]:
                    raise ValueError("Invalid MP4 evidence")
                payload["evidence_videos"].append({"path": entry.filename,
                    "sha256": hashlib.sha256(media).hexdigest(), "media_type": "video/mp4",
                    "source": "Android screenrecord", "data_url": "data:video/mp4;base64," + base64.b64encode(media).decode()})
            if "checkpoints" in name.parts or name.name in {"hosted_verdict.json", "provenance.json", "installed_apk.json", "recording.json"}:
                payload["saved_logs"][entry.filename] = archive.read(entry).decode()
    if len(json.dumps(payload).encode()) > MAX_DASHBOARD_BYTES:
        raise ValueError("DASHBOARD_PAYLOAD_TOO_LARGE: archive remains saved; do not silently omit evidence")
    return payload


class HostedSession:
    def __init__(self, output, image=DEFAULT_IMAGE, client=None, inspection=False, rubric_profile="peach_strict_v1", attempt_id=None, acceleration="kvm", bootstrap_runtime=False):
        if rubric_profile not in {"legacy_v1", "peach_strict_v1"}:
            raise ValueError("Unknown rubric profile")
        self.options = runtime_options(acceleration)
        self.rubric_profile = rubric_profile
        self.inspection = inspection is True
        self.bootstrap_runtime = bootstrap_runtime is True
        if self.bootstrap_runtime and (image != "ubuntu:24.04" or acceleration != "software"):
            raise ValueError("Bootstrap requires ubuntu:24.04 and explicit software mode")
        if not self.bootstrap_runtime and (not isinstance(image, str) or not re.fullmatch(r"prime/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+", image)):
            raise ValueError("Use an explicit versioned Prime image reference")
        self.run_id, self.image = uuid4().hex, image
        self.root = Path(output).resolve() / self.run_id
        self.root.mkdir(parents=True, exist_ok=False)
        self.remote = RUNTIME / self.run_id
        self.client = client
        self.sandbox_id, self.sequence, self.finished = None, 0, None
        self.started = False
        self.pending_request = None
        self.info = {"execution_location": "prime-vm-sandbox", "sandbox_image": image,
                     "artifacts": str(self.root), "reward_timeline": [],
                     "rubric_profile": rubric_profile, "attempt_id": attempt_id,
                     "emulator_runtime": self.options,
                     "run_kind": "manual_ui_inspection" if self.inspection else "model_evaluation"}

    def persist(self):
        # This file contains provenance and lifecycle receipts, never API secrets.
        summary = {key: value for key, value in self.info.items()
                   if key not in {"evidence_archive", "evidence_videos", "saved_logs"}}
        (self.root / "hosted_session.json").write_text(json.dumps(summary, indent=2))

    def start(self):
        from prime_sandboxes import CreateSandboxRequest
        if self.client is None:
            self.client = sdk_client(self.root / ".prime-cache")
        request = CreateSandboxRequest(name="democart-" + self.run_id[:12], docker_image=self.image,
            vm=True, cpu_cores=4, memory_gb=8, disk_size_gb=32, timeout_minutes=self.options["sandbox_timeout_minutes"],
            idempotency_key="democart-" + self.run_id, region="us", labels=["democart-peach", "one-rollout"])
        sandbox = self.client.create(request)
        self.sandbox_id = sandbox.id
        self.info.update(sandbox_id=self.sandbox_id, sandbox_timeout_minutes=self.options["sandbox_timeout_minutes"])
        self.persist()
        self.client.wait_for_creation(self.sandbox_id, max_attempts=60, image_build_timeout_seconds=120)
        if self.bootstrap_runtime:
            from amazon_cart_001.integrations.runtime_bootstrap import provision
            provision(self)
        command = shlex.join(["python", "-m", MODULE, "serve", "--root", str(self.remote),
                              "--rubric-profile", self.rubric_profile, "--acceleration", self.options["acceleration"]] +
                             (["--inspection"] if self.inspection else []))
        self.client.execute_command(self.sandbox_id, shlex.join(["mkdir", "-p", str(self.remote)]), timeout=30)
        job = self.client.start_background_job(self.sandbox_id, command, **self.command_environment())
        self.info["worker_job_id"] = job.job_id
        self.started = True
        self.persist()
        return self.call("reset")

    def command_environment(self):
        if self.bootstrap_runtime:
            from amazon_cart_001.integrations.runtime_bootstrap import REMOTE_ENV
            return {"env": REMOTE_ENV}
        return {}

    def download(self, receipt, destination, expected, limit):
        if not isinstance(receipt, dict) or receipt.get("path") != str(expected):
            raise ValueError("Unexpected worker evidence path")
        size = receipt.get("bytes")
        if type(size) is not int or not 0 < size <= limit:
            raise ValueError("Invalid worker evidence size")
        self.client.download_file(self.sandbox_id, str(expected), str(destination))
        data = destination.read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != receipt.get("sha256"):
            raise ValueError("Evidence download hash or length mismatch")
        return data

    def call(self, operation, action=None):
        if self.pending_request is not None:
            raise RuntimeError("Unresolved worker request; reconcile before another operation")
        index = self.sequence
        request = {"sequence": index, "operation": operation}
        if operation == "step":
            request["action"] = action
        path = self.root / f"request-{index:03d}.json"
        path.write_text(json.dumps(request))
        self.pending_request = request
        self.info["pending_request"] = {"sequence": index, "operation": operation}
        self.persist()
        self.client.upload_file(self.sandbox_id, str(self.remote / f"request-{index:03d}.incoming"), str(path))
        return self.receive_pending(self.options["exchange_timeout_seconds"])

    def receive_pending(self, timeout):
        """Poll the immutable mailbox; never resubmit or replay the actor action."""
        if self.pending_request is None:
            raise RuntimeError("No pending worker request")
        index = self.pending_request["sequence"]
        command = shlex.join(["python", "-m", MODULE, "exchange", "--root", str(self.remote),
                              "--sequence", str(index), "--acceleration", self.options["acceleration"], "--poll"])
        deadline = time.monotonic() + timeout
        transport_errors = 0
        while time.monotonic() < deadline:
            try:
                result = self.client.execute_command(
                    self.sandbox_id, command, timeout=min(30, max(1, int(deadline-time.monotonic()))),
                    **self.command_environment())
            except Exception as exc:
                if not isinstance(exc, (TimeoutError, ConnectionError)) and type(exc).__name__ != "APIError":
                    raise
                transport_errors += 1
                self.info.setdefault("transport_recovery", []).append({
                    "sequence": index, "operation": self.pending_request["operation"],
                    "error_type": type(exc).__name__, "poll_error_number": transport_errors})
                self.persist()
                if transport_errors >= 3:
                    raise
                time.sleep(min(2, max(0, deadline-time.monotonic())))
                continue
            if result.exit_code != 0:
                raise RuntimeError("Worker exchange failed: " + result.stderr[:2000])
            receipt = json.loads(result.stdout)
            if receipt.get("pending") is True:
                if receipt != {"pending": True, "sequence": index}:
                    raise ValueError("Malformed pending response")
                time.sleep(min(2, max(0, deadline-time.monotonic())))
                continue
            data = self.download(receipt, self.root / f"response-{index:03d}.json",
                                 self.remote / f"response-{index:03d}.json", MAX_RESPONSE)
            response = json.loads(data)
            if type(response.get("sequence")) is not int or response["sequence"] != index:
                raise ValueError("Worker response belongs to another action")
            if type(response.get("ok")) is not bool:
                raise ValueError("Worker response lacks explicit status")
            self.sequence = index + 1
            self.pending_request = None
            self.info.pop("pending_request", None)
            self.persist()
            if response["ok"] is not True:
                raise RuntimeError(response.get("error", "Unknown worker failure"))
            value = response["result"]
            if "checkpoint" in value:
                self.info["reward_timeline"].append(value["checkpoint"])
                self.info["episode_id"] = value["episode_id"]
            self.persist()
            return value
        raise TimeoutError("Worker response deadline exceeded; request remains pending")

    def live_frame(self):
        if not self.started or self.finished is not None:
            raise RuntimeError("Live Android session is not running")
        command = shlex.join(["python", "-m", "amazon_cart_001.harness.live_device",
                              "capture", "--root", str(self.remote)])
        result = self.client.execute_command(self.sandbox_id, command, timeout=30, **self.command_environment())
        if result.exit_code != 0:
            raise RuntimeError("Live capture failed; worker diagnostics retained")
        frame = json.loads(result.stdout)
        if (frame.get("episode_id") != self.info.get("episode_id") or
                frame.get("interactive") is not self.inspection):
            raise ValueError("Live frame belongs to another episode or control mode")
        frame_id = frame.get("frame_id")
        if not isinstance(frame_id, str) or re.fullmatch(r"[a-f0-9]{32}", frame_id) is None:
            raise ValueError("Unexpected live frame identity")
        destination = self.root / ("live-" + frame_id + ".png")
        try:
            data = self.download(frame, destination, self.remote / "live" / (frame_id + ".png"), MAX_RESPONSE)
            return frame, data
        finally:
            destination.unlink(missing_ok=True)

    def live_control(self, payload):
        if not self.inspection or not self.started or self.finished is not None:
            raise PermissionError("Human control is restricted to running UI inspection sessions")
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        if len(encoded) > 4096:
            raise ValueError("Control payload too large")
        command = shlex.join(["python", "-m", "amazon_cart_001.harness.live_device",
            "control", "--root", str(self.remote), "--payload", encoded])
        result = self.client.execute_command(self.sandbox_id, command, timeout=30)
        if result.exit_code != 0:
            raise ValueError("Control rejected by the worker; refresh the frame before retrying")
        return json.loads(result.stdout)

    def finish(self, error=None):
        if self.finished is not None:
            return self.finished
        verdict = invalid("HOSTED_SETUP_INCOMPLETE")
        try:
            if self.started:
                if self.pending_request is not None:
                    try:
                        self.receive_pending(60)
                    except Exception as exc:
                        self.info["pending_recovery_error"] = type(exc).__name__
                        if self.pending_request is not None:
                            raise
                        error = error or "Worker reported failure during cleanup reconciliation"
                final = self.call("finalize")
                verdict = final["verdict"]
                archive = self.root / "evidence.zip"
                self.download(final["archive"], archive, self.remote / "evidence.zip", MAX_ARCHIVE)
                self.info.update(archive_payload(archive))
                self.info["evidence_export_verified"] = True
            if error:
                self.info["task_verdict_before_pipeline_gate"] = verdict
                verdict = invalid("HOSTED_PIPELINE_ERROR: " + str(error))
        except Exception as exc:
            self.info["task_verdict_before_pipeline_gate"] = verdict
            verdict = invalid("HOSTED_EXPORT_ERROR: " + str(exc))
        finally:
            if self.sandbox_id:
                try:
                    self.client.delete(self.sandbox_id)
                    self.info["sandbox_deleted"] = True
                except Exception as exc:
                    self.info["sandbox_deleted"] = False
                    self.info["cleanup_error"] = str(exc)
                    self.info["task_verdict_before_cleanup_gate"] = verdict
                    verdict = invalid("SANDBOX_DELETE_FAILED: " + str(exc))
            self.info["episode_verdict"] = verdict
            # Keep large dashboard payloads out of the lightweight lifecycle log.
            self.persist()
            self.finished = verdict
        return verdict


