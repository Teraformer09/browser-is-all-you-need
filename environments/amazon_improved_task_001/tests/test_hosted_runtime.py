"""Offline contract tests: never start Android, a sandbox or a model."""
import asyncio
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

from amazon_improved_task_001 import load_environment
from amazon_improved_task_001.harness.hosted_worker import Worker, check_root, exchange, validate_request, write_json
from amazon_improved_task_001.integrations.hosted_env import HostedAmazonCartEnv
from amazon_improved_task_001.integrations.hosted_session import HostedSession, archive_payload


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def session(self):
        return HostedSession(self.root, client=Mock())

    def test_default_loader_is_peach_hosted_but_does_not_run(self):
        with patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
            env = load_environment()
            self.assertIsInstance(env, HostedAmazonCartEnv)
            self.assertFalse(env.allow_eval)
            self.assertEqual(env.max_turns, 19)
            self.assertEqual(len(env.eval_dataset), 1)
            session.assert_not_called()

    def test_action_budget_profile_is_default_and_attempts_are_bounded(self):
        env = load_environment(allow_eval=True, live_viewer=False)
        self.assertEqual(env.rubric_profile, "peach_action_budget_v1")
        env.attempt_count = 12
        with patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
            with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
                asyncio.run(env.setup_state({"trajectory_id": "blocked-13"}))
            session.assert_not_called()
        for kwargs in ({"max_attempts":13}, {"max_attempts":True}, {"rubric_profile":"guess"}):
            with self.assertRaises(ValueError):
                load_environment(**kwargs)

    def test_worker_command_pins_strict_profile(self):
        session = self.session()
        session.client.create.return_value = SimpleNamespace(id="sandbox-test")
        session.client.start_background_job.return_value = SimpleNamespace(job_id="job-test")
        with patch.object(session, "call", return_value={}):
            session.start()
        self.assertIn("--rubric-profile peach_strict_v1", session.client.start_background_job.call_args.args[1])

    def test_approval_guard_precedes_session_creation(self):
        env = load_environment()
        with patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
            with self.assertRaisesRegex(RuntimeError, "allow_eval"):
                asyncio.run(env.setup_state({"trajectory_id": "test"}))
            session.assert_not_called()

    def test_viewer_secret_guard_precedes_billed_session(self):
        env = load_environment(allow_eval=True)
        with patch.dict("os.environ", {}, clear=True), \
             patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
            with self.assertRaisesRegex(RuntimeError, "DEMOCART_VIEWER_TOKEN"):
                asyncio.run(env.setup_state({"trajectory_id": "test"}))
            session.assert_not_called()

    def test_explicit_legacy_mode_still_loads(self):
        self.assertEqual(type(load_environment(execution="legacy_local_adb")).__name__, "AmazonCart001Env")
        with self.assertRaises(ValueError):
            load_environment(execution="silently-local")

    def test_only_versioned_prime_images(self):
        for image in ("ubuntu:latest", "prime/u/name", "prime/u/a:v1; echo oops", None):
            with self.subTest(image=image), self.assertRaises(ValueError):
                HostedSession(self.root, image, client=Mock())

    def test_request_schema(self):
        validate_request({"sequence": 0, "operation": "reset"}, 0)
        validate_request({"sequence": 1, "operation": "step", "action": "[]"}, 1)
        for request in ([], None, {"sequence": True, "operation": "reset"},
                        {"sequence": 1, "operation": "shell"},
                        {"sequence": 0, "operation": "reset", "command": "adb"}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                validate_request(request, 0)

    def test_remote_paths_are_single_private_run(self):
        check_root("/data/Tirtha/democart-runtime/" + "a" * 32)
        for path in ("/", "/data/Tirtha", "/data/Tirtha/democart-runtime/../other"):
            with self.assertRaises(ValueError):
                check_root(path)

    def test_mailbox_retry_returns_same_response_without_replaying(self):
        request = {"sequence": 1, "operation": "step", "action": '{"type":"wait"}'}
        write_json(self.root / "request-001.json", request)
        write_json(self.root / "request-001.incoming", request)
        write_json(self.root / "response-001.json", {"sequence": 1, "ok": True, "result": {}})
        with contextlib.redirect_stdout(io.StringIO()) as output:
            exchange(self.root, 1)
        self.assertEqual(json.loads(output.getvalue())["path"], str(self.root / "response-001.json"))
        request["action"] = '{"type":"finish"}'
        write_json(self.root / "request-001.incoming", request)
        with self.assertRaisesRegex(RuntimeError, "Conflicting retry"):
            exchange(self.root, 1)

    def test_bound_vm_resources_no_credentials_in_worker(self):
        session = self.session()
        session.client.create.return_value = SimpleNamespace(id="sandbox-one")
        session.client.start_background_job.return_value = SimpleNamespace(job_id="job-one")
        with patch.object(session, "call", return_value={"done": False}):
            session.start()
        request = session.client.create.call_args.args[0]
        self.assertTrue(request.vm)
        self.assertEqual((request.cpu_cores, request.memory_gb, request.disk_size_gb, request.timeout_minutes), (4, 8, 32, 20))
        self.assertIsNone(request.secrets)
        self.assertIsNone(request.environment_vars)
        self.assertEqual(session.info["sandbox_id"], "sandbox-one")

    def test_wait_failure_still_deletes_created_vm(self):
        session = self.session()
        session.client.create.return_value = SimpleNamespace(id="sandbox-one")
        session.client.wait_for_creation.side_effect = RuntimeError("VM unavailable")
        with self.assertRaisesRegex(RuntimeError, "VM unavailable"):
            session.start()
        result = session.finish("VM unavailable")
        self.assertEqual(result["status"], "INVALID")
        session.client.delete.assert_called_once_with("sandbox-one")

    def test_create_credit_error_creates_no_cleanup_target(self):
        session = self.session()
        session.client.create.side_effect = RuntimeError("402 Insufficient credits")
        with self.assertRaisesRegex(RuntimeError, "402"):
            session.start()
        self.assertEqual(session.finish("402 Insufficient credits")["reward"], 0)
        session.client.delete.assert_not_called()

    def test_export_precedes_delete_and_finalize_is_idempotent(self):
        session = self.session()
        session.sandbox_id, session.started = "sandbox-one", True
        events = []
        with patch.object(session, "call", side_effect=lambda *a: events.append("finalize") or {
                "verdict": {"status": "PASS", "reward": 1}, "archive": {}}), \
             patch.object(session, "download", side_effect=lambda *a: events.append("download")), \
             patch("amazon_improved_task_001.integrations.hosted_session.archive_payload", return_value={}):
            session.client.delete.side_effect = lambda *a: events.append("delete")
            self.assertEqual(session.finish()["reward"], 1)
            self.assertEqual(session.finish()["reward"], 1)
        self.assertEqual(events, ["finalize", "download", "delete"])

    def test_export_failure_invalidates_and_deletes(self):
        session = self.session()
        session.sandbox_id, session.started = "sandbox-one", True
        with patch.object(session, "call", side_effect=RuntimeError("missing essential media")):
            result = session.finish()
        self.assertEqual(result["status"], "INVALID")
        self.assertFalse(result["training_eligible"])
        session.client.delete.assert_called_once()

    def test_cleanup_failure_is_visible(self):
        session = self.session()
        session.sandbox_id = "sandbox-one"
        session.client.delete.side_effect = RuntimeError("transport")
        self.assertIn("SANDBOX_DELETE_FAILED", session.finish()["reason_codes"][0])
        self.assertFalse(session.info["sandbox_deleted"])

    def test_download_path_size_and_hash(self):
        session = self.session()
        output, expected = session.root / "download", session.remote / "response-000.json"
        data = b'{"ok":true}'
        receipt = {"path": str(expected), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        session.client.download_file.side_effect = lambda *a: output.write_bytes(data)
        self.assertEqual(session.download(receipt, output, expected, 100), data)
        receipt["sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "hash"):
            session.download(receipt, output, expected, 100)
        receipt["path"] = "/etc/passwd"
        with self.assertRaisesRegex(ValueError, "path"):
            session.download(receipt, output, expected, 100)

    def test_archive_exports_original_video_and_policy_checkpoint(self):
        path = self.root / "evidence.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr("episodes/one/video/screen-recording.mp4", b"\x00\x00\x00\x18ftypmp42original")
            archive.writestr("episodes/one/checkpoints/000.json", '{"episode_reward":null}')
        payload = archive_payload(path)
        self.assertEqual(len(payload["evidence_videos"]), 1)
        self.assertIn("episodes/one/checkpoints/000.json", payload["saved_logs"])
        self.assertEqual(payload["evidence_archive"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_unsafe_zip_rejected_without_extraction(self):
        path = self.root / "unsafe.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr("../escape", "bad")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            archive_payload(path)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_kvm_required_before_launch(self):
        worker = Worker(self.root)
        with patch.object(Path, "is_char_device", return_value=False), patch.object(worker, "command") as command:
            with self.assertRaisesRegex(RuntimeError, "KVM_UNAVAILABLE"):
                worker.boot()
            command.assert_not_called()
