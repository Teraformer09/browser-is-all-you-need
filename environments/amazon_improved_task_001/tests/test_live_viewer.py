"""Local-only security/interaction tests; no Prime tunnel, model or Android VM."""
import base64
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amazon_improved_task_001.harness.hosted_worker import Worker, write_json
from amazon_improved_task_001.harness.live_device import capture, control
from amazon_improved_task_001.integrations.live_viewer import LiveViewer
from amazon_improved_task_001.integrations.hosted_session import HostedSession
from amazon_improved_task_001.integrations.viewer_tunnel import private_json, ViewerTunnel

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=")


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frame = {"frame_id": "a" * 32, "sha256": hashlib.sha256(PNG).hexdigest(),
                      "width": 1, "height": 1, "episode_id": "episode", "captured_at": time.time()}

    def viewer(self, interactive=False):
        self.callback = Mock(return_value={"accepted": True})
        viewer = LiveViewer(lambda: (self.frame, PNG), self.callback if interactive else None,
                            interactive=interactive, interval=60, label="OFFLINE TEST FIXTURE")
        self.addCleanup(viewer.stop_local)
        port = viewer.start_local()
        self.url = "http://127.0.0.1:" + str(port)
        return viewer

    def request(self, path, viewer=None, body=None, mime="application/json"):
        headers = {"Authorization": "Bearer " + viewer.token} if viewer else {}
        if body is not None:
            headers["Content-Type"] = mime
        request = Request(self.url + path, data=body, headers=headers)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read(), response.headers
        except HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def test_no_unauthenticated_screen_or_status(self):
        self.viewer()
        for path in ("/api/status", "/api/frame"):
            self.assertEqual(self.request(path)[0], 401)

    def test_static_login_contains_no_token(self):
        viewer = self.viewer()
        status, data, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertNotIn(viewer.token.encode(), data)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_authenticated_frame_is_original_bytes(self):
        viewer = self.viewer()
        status, data, _ = self.request("/api/frame?frame_id=" + self.frame["frame_id"], viewer)
        self.assertEqual((status, data), (200, PNG))

    def test_mismatched_frame_request_is_rejected(self):
        viewer = self.viewer()
        self.assertEqual(self.request("/api/frame?frame_id=changed", viewer)[0], 409)

    def test_readonly_blocks_controls_even_with_token(self):
        viewer = self.viewer()
        self.assertEqual(self.request("/api/control", viewer, b'{"type":"tap"}')[0], 403)
        self.callback.assert_not_called()

    def test_no_token_no_control(self):
        self.viewer(True)
        self.assertEqual(self.request("/api/control", body=b'{}')[0], 401)
        self.callback.assert_not_called()

    def test_interactive_control_and_rate_limit(self):
        viewer = self.viewer(True)
        body = json.dumps({"type": "tap", "frame_id": self.frame["frame_id"], "x": 0, "y": 0}).encode()
        self.assertEqual(self.request("/api/control", viewer, body)[0], 200)
        self.callback.assert_called_once_with(json.loads(body))
        self.assertEqual(self.request("/api/control", viewer, body)[0], 429)

    def test_reject_oversized_or_non_json_input(self):
        viewer = self.viewer(True)
        self.assertEqual(self.request("/api/control", viewer, b"x" * 2049)[0], 413)
        self.assertEqual(self.request("/api/control", viewer, b'{}', mime="text/plain")[0], 415)
        self.callback.assert_not_called()

    def test_stale_frame_not_claimed_connected(self):
        viewer = self.viewer()
        viewer.received_at -= 20
        status = json.loads(self.request("/api/status", viewer)[1])
        self.assertFalse(status["connected"])
        self.assertGreater(status["frame_age_seconds"], 10)

    def test_repeated_frame_does_not_reset_freshness(self):
        viewer = self.viewer()
        viewer.received_at -= 20
        original = viewer.received_at
        viewer.update()
        self.assertEqual(viewer.received_at, original)
        self.assertFalse(viewer.status()["connected"])

    def test_freshness_includes_capture_transport_latency(self):
        viewer = LiveViewer(lambda: (self.frame, PNG))
        with patch("amazon_improved_task_001.integrations.live_viewer.time.monotonic", side_effect=[10, 25]):
            viewer.update()
            self.assertFalse(viewer.status()["connected"])

    def test_explicit_access_token_validation(self):
        token = "testOnly_" + "a" * 35
        self.assertEqual(LiveViewer(lambda: (self.frame, PNG), access_token=token).token, token)
        for value in ("short", " " * 43, True, "a" * 129):
            with self.subTest(value=value), self.assertRaises(ValueError):
                LiveViewer(lambda: (self.frame, PNG), access_token=value)

    def test_live_frame_requires_matching_episode_and_mode(self):
        for frame in ({"episode_id": "other", "interactive": False},
                      {"episode_id": "episode", "interactive": True}):
            session = HostedSession(self.root, client=Mock())
            session.started = True
            session.info["episode_id"] = "episode"
            session.client.execute_command.return_value = SimpleNamespace(
                exit_code=0, stdout=json.dumps(frame))
            with self.subTest(frame=frame), self.assertRaisesRegex(ValueError, "another episode"):
                session.live_frame()
            session.client.download_file.assert_not_called()

    def test_capture_error_preserves_explicit_staleness(self):
        viewer = self.viewer()
        viewer.capture = Mock(side_effect=RuntimeError("transport down"))
        viewer.update()
        self.assertFalse(viewer.status()["connected"])
        self.assertIn("transport down", viewer.status()["error"])

    def test_path_traversal_not_served(self):
        viewer = self.viewer()
        self.assertEqual(self.request("/../../.prime/config.json", viewer)[0], 404)

    def test_closed_token_revoked(self):
        viewer = self.viewer()
        original = viewer.token
        viewer.stop_local()
        self.assertNotEqual(original, viewer.token)
        self.assertFalse(viewer.status()["connected"])

    def write_worker_state(self, inspection):
        write_json(self.root / "viewer_state.json", {"running": True, "inspection": inspection, "episode_id": "episode"})
        (self.root / "live").mkdir(exist_ok=True)
        write_json(self.root / "live" / (self.frame["frame_id"] + ".json"), self.frame)

    def test_worker_independently_rejects_eval_controls(self):
        self.write_worker_state(False)
        device = Mock()
        with self.assertRaisesRegex(PermissionError, "READ_ONLY"):
            control(self.root, {}, device)
        device.command.assert_not_called()

    def test_worker_inspection_tap_is_logged_not_scored(self):
        self.write_worker_state(True)
        device = Mock()
        payload = {"type": "tap", "frame_id": self.frame["frame_id"], "x": 0, "y": 0}
        self.assertFalse(control(self.root, payload, device)["evaluation"])
        device.command.assert_called_once_with("shell", "input", "tap", "0", "0")
        self.assertEqual(json.loads((self.root / "viewer-controls.log").read_text())["kind"], "manual_ui_inspection")

    def test_worker_rejects_stale_control(self):
        self.frame["captured_at"] -= 10
        self.write_worker_state(True)
        with self.assertRaisesRegex(ValueError, "STALE"):
            control(self.root, {"frame_id": self.frame["frame_id"], "type": "back"}, Mock())

    def test_worker_rejects_out_of_bounds_and_injection(self):
        self.write_worker_state(True)
        for payload in ({"type": "tap", "x": True, "y": 0}, {"type": "tap", "x": 1, "y": 0},
                        {"type": "text", "text": "hello; reboot"}, {"type": "shell", "command": "id"}):
            device = Mock()
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                control(self.root, {**payload, "frame_id": self.frame["frame_id"]}, device)
            device.command.assert_not_called()

    def test_capture_png_validation(self):
        self.write_worker_state(False)
        device = Mock()
        device.command.return_value = PNG
        receipt = capture(self.root, device)
        self.assertEqual(receipt["sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertFalse(receipt["interactive"])
        device.command.return_value = b"not a PNG"
        with self.assertRaises(ValueError):
            capture(self.root, device)

    def test_live_cache_is_bounded(self):
        self.write_worker_state(False)
        device = Mock()
        device.command.return_value = PNG
        for _ in range(11):
            capture(self.root, device)
        self.assertEqual(len(list((self.root / "live").glob("*.json"))), 8)
        self.assertLessEqual(len(list((self.root / "live").glob("*.png"))), 8)

    def test_session_gate_rejects_manual_input_during_eval(self):
        session = HostedSession(self.root, client=Mock())
        session.started = True
        with self.assertRaises(PermissionError):
            session.live_control({})
        session.client.execute_command.assert_not_called()

    def test_inspection_finalization_never_calls_reward_verifier(self):
        worker = Worker(self.root, inspection=True)
        worker.env = Mock()
        worker.env.root = self.root / "episode"
        worker.env.root.mkdir()
        result = worker.finalize()
        self.assertEqual(result["verdict"]["status"], "NOT_SCORED")
        self.assertIsNone(result["verdict"]["reward"])
        worker.env.finalize.assert_not_called()

    def test_private_access_permissions(self):
        path = self.root / "private" / "access.json"
        private_json(path, {"token": "test-only"})
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o700)

    def test_tunnel_config_never_uses_global_home(self):
        with patch("prime_tunnel.core.client.TunnelClient"):
            tunnel = ViewerTunnel(12345, self.root / "private")
        tunnel.info = SimpleNamespace(server_host="example.pinfra.io", server_port=7000,
            tunnel_id="test-only", frp_token='quoted"test', binding_secret="binding-test")
        path = tunnel.config()
        self.assertTrue(path.is_relative_to(self.root))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        import tomllib
        self.assertEqual(tomllib.loads(path.read_text())["auth"]["token"], 'quoted"test')


if __name__ == "__main__":
    unittest.main()
