"""Offline regressions for complete exports and free-provider retry handling."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock

from uber_clone_031.agents.openrouter import request_completion

spec = importlib.util.spec_from_file_location("upload_evidence", Path(__file__).parents[1] / "uber_clone_031/integrations/prime_upload.py")
upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload)


class UploadAndRetryTests(unittest.TestCase):
    def test_429_retries_same_request_then_succeeds(self):
        error = urllib.error.HTTPError("https://openrouter.ai", 429, "rate limit", {"Retry-After":"25"}, io.BytesIO(b'{"error":"busy"}'))
        opener = Mock(side_effect=[error, io.BytesIO(b'{"choices":[]}')])
        sleep = Mock()
        request = object()
        data, retries = request_completion(request, opener=opener, sleeper=sleep)
        self.assertEqual(data, {"choices":[]})
        self.assertEqual(len(retries), 1)
        self.assertTrue(all(call.args[0] is request for call in opener.call_args_list))
        sleep.assert_called_once_with(25)

    def test_retries_are_bounded_and_never_hide_terminal_error(self):
        errors = [urllib.error.HTTPError("https://openrouter.ai", 429, "busy", {}, io.BytesIO(b'busy')) for _ in range(3)]
        opener, sleep = Mock(side_effect=errors), Mock()
        with self.assertRaisesRegex(RuntimeError, "HTTP 429 after 3"):
            request_completion(object(), opener=opener, sleeper=sleep)
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_authentication_error_does_not_retry(self):
        error = urllib.error.HTTPError("https://openrouter.ai", 401, "auth", {}, io.BytesIO(b'unauthorized'))
        opener, sleep = Mock(side_effect=error), Mock()
        with self.assertRaisesRegex(RuntimeError, "HTTP 401 after 1"):
            request_completion(object(), opener=opener, sleeper=sleep)
        sleep.assert_not_called()

    def make_run(self, root):
        (root / "screenshots").mkdir()
        png = b"\x89PNG\r\n\x1a\nfixture"
        (root / "screenshots/000.png").write_bytes(png)
        frame = {"index":0, "action":None, "screenshot":{"path":"screenshots/000.png", "sha256":hashlib.sha256(png).hexdigest()}}
        sample = {"reward":0, "info":{"manifest":{"frames":[frame]}}}
        (root / "results.jsonl").write_text(json.dumps(sample))
        (root / "metadata.json").write_text(json.dumps({"policy":"openrouter", "model_calls":1, "elapsed_seconds":2}))
        for name in ("trajectory.jsonl", "adb_actions.jsonl", "stage_history.json", "verdict.json", "verifier_results.json", "verifier_context.json", "initial_state.json", "final_state.json", "installed_apk.json", "model_calls.json", "manifest.json"):
            (root / name).write_text("{}")

    def test_round_trip_checks_every_frame_and_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            sample, _, expected = upload.prepare_sample(root)
            remote = {"samples":[copy.deepcopy(sample)]}
            self.assertTrue(upload.verify_remote(remote, sample, expected)["screenshot_frames_verified"])
            remote["samples"][0]["info"]["evidence_images"] = []
            self.assertFalse(upload.verify_remote(remote, sample, expected)["screenshot_frames_verified"])
            remote["samples"][0]["info"]["saved_logs"]["verdict.json"] = "changed"
            self.assertFalse(upload.verify_remote(remote, sample, expected)["saved_logs_verified"])

    def test_modified_png_prevents_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            (root / "screenshots/000.png").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "integrity"):
                upload.prepare_sample(root)

    def test_explicit_payload_cap_never_drops_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            original, _, expected = upload.prepare_sample(root)
            with self.assertRaisesRegex(ValueError, "no partial upload"):
                upload.prepare_sample(root, max_payload_bytes=1)
            enlarged, _, actual = upload.prepare_sample(root, max_payload_bytes=64 * 1024 * 1024)
            self.assertEqual(enlarged, original)
            self.assertEqual(actual, expected)
            with self.assertRaisesRegex(ValueError, "at most 64"):
                upload.prepare_sample(root, max_payload_bytes=65 * 1024 * 1024)

    def test_conversation_image_is_referenced_without_losing_a_frame(self):
        import base64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            data_url = "data:image/png;base64," + base64.b64encode(
                (root / "screenshots/000.png").read_bytes()).decode()
            source = json.loads((root / "results.jsonl").read_text())
            source["prompt"] = [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}}]}]
            (root / "results.jsonl").write_text(json.dumps(source))
            sample, _, expected = upload.prepare_sample(root)
            frame = sample["info"]["evidence_images"][0]
            self.assertEqual(frame["message_ref"], "/prompt/0/content/0")
            self.assertNotIn("data_url", frame)
            self.assertEqual(json.dumps(sample).count(data_url), 1)
            remote = {"samples": [copy.deepcopy(sample)]}
            self.assertTrue(upload.verify_remote(remote, sample, expected)["screenshot_frames_verified"])
            remote["samples"][0]["prompt"][0]["content"] = json.dumps(
                remote["samples"][0]["prompt"][0]["content"])
            self.assertTrue(upload.verify_remote(remote, sample, expected)["screenshot_frames_verified"])
            remote["samples"][0]["info"]["evidence_images"][0]["message_ref"] = "/outside/0"
            self.assertFalse(upload.verify_remote(remote, sample, expected)["screenshot_frames_verified"])

    def test_credential_in_trace_prevents_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            (root / "adb_actions.jsonl").write_text("pit_" + "a" * 40)
            with self.assertRaisesRegex(ValueError, "Credential"):
                upload.prepare_sample(root)


if __name__ == "__main__":
    unittest.main()
