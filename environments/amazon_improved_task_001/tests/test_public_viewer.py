"""Public read-only viewer checks. Local fixtures only: no Prime/model/Android."""
import asyncio
import base64
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amazon_improved_task_001 import load_environment
from amazon_improved_task_001.integrations.live_viewer import LiveViewer
from amazon_improved_task_001.integrations.viewer_tunnel import ViewerTunnel, start_viewer

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=")


class PublicViewerTests(unittest.TestCase):
    def viewer(self, **kwargs):
        frame = {"frame_id": "public-test", "sha256": hashlib.sha256(PNG).hexdigest(),
                 "width": 1, "height": 1, "captured_at": time.time()}
        viewer = LiveViewer(lambda: (frame, PNG), public_readonly=True, interval=60, test_fixture=True, **kwargs)
        self.addCleanup(viewer.stop_local)
        self.url = "http://127.0.0.1:" + str(viewer.start_local())
        return viewer

    def request(self, path, *, method="GET", headers=None):
        request = Request(self.url + path, method=method, headers=headers or {},
                          data=b'{}' if method == "POST" else None)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def test_public_mode_and_original_screen_need_no_token(self):
        viewer = self.viewer()
        self.assertEqual(viewer.token, "")
        mode = json.loads(self.request("/api/viewer-mode")[1])
        self.assertEqual(mode, {"public_readonly": True, "authentication_required": False})
        status = json.loads(self.request("/api/status")[1])
        self.assertTrue(status["connected"])
        self.assertTrue(status["public_readonly"])
        self.assertTrue(status["evaluation_control_disabled"])
        self.assertFalse(status["interactive"])
        code, image, headers = self.request("/api/frame?frame_id=public-test")
        self.assertEqual((code, image), (200, PNG))
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_every_public_post_is_rejected_with_or_without_auth(self):
        self.viewer()
        for path in ("/api/control", "/api/reset", "/anywhere"):
            for headers in ({}, {"Authorization": "Bearer ignored"}):
                self.assertEqual(self.request(path, method="POST", headers=headers)[0], 403)

    def test_unknown_paths_never_serve_private_files(self):
        self.viewer()
        for path in ("/.viewer-private/access.json", "/api/logs", "/../../.prime/config.json"):
            self.assertEqual(self.request(path)[0], 404)

    def test_public_errors_do_not_disclose_transport_details(self):
        viewer = self.viewer()
        viewer.capture = Mock(side_effect=RuntimeError("secret_token=test-only-private; /internal/path"))
        viewer.update()
        body = self.request("/api/status")[1]
        self.assertNotIn(b"test-only-private", body)
        self.assertNotIn(b"/internal/path", body)
        self.assertFalse(json.loads(body)["connected"])

    def test_public_staleness_and_frame_identity_are_preserved(self):
        viewer = self.viewer()
        viewer.received_at -= 20
        viewer.update()
        self.assertFalse(json.loads(self.request("/api/status")[1])["connected"])
        self.assertEqual(self.request("/api/frame?frame_id=other")[0], 409)

    def test_public_inspection_and_secret_combinations_are_rejected(self):
        for kwargs in ({"interactive": True, "control": Mock()}, {"control": Mock()},
                       {"access_token": "a" * 43}, {"public_readonly": "true"}):
            config = {"public_readonly": True, **kwargs}
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LiveViewer(Mock(), **config)

    def test_public_hosted_mode_skips_only_viewer_secret_guard(self):
        env = load_environment(allow_eval=True, public_viewer=True)
        session = Mock(info={})
        session.start.return_value = {"message": {"role": "user", "content": "offline fixture"}}
        async def fake_viewer(current, **kwargs):
            self.assertIs(current, session)
            self.assertEqual(kwargs, {"interactive": False, "public_readonly": True})
            current.info["live_viewer"] = {"url": "https://offline.invalid", "access_mode": "public_readonly"}
            return Mock()
        with patch.dict("os.environ", {}, clear=True), \
             patch("amazon_improved_task_001.integrations.hosted_env.HostedSession", return_value=session), \
             patch("amazon_improved_task_001.integrations.hosted_env.start_viewer", side_effect=fake_viewer):
            asyncio.run(env.setup_state({"trajectory_id": "public-offline", "prompt": []}))
        session.start.assert_called_once()
        self.assertEqual(env.attempt_count, 1)

    def test_public_mode_does_not_bypass_compute_opt_in(self):
        env = load_environment(public_viewer=True)
        with patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
            with self.assertRaisesRegex(RuntimeError, "allow_eval"):
                asyncio.run(env.setup_state({"trajectory_id": "not-authorized"}))
            session.assert_not_called()
        for kwargs in ({"public_viewer": "true"}, {"public_viewer": True, "live_viewer": False}):
            with self.assertRaises(ValueError):
                load_environment(**kwargs)

    def test_tunnel_attests_public_png_and_denied_input_without_access_file(self):
        with tempfile.TemporaryDirectory() as temp, patch("prime_tunnel.core.client.TunnelClient"):
            tunnel = ViewerTunnel(1234, Path(temp))
            tunnel.client.create_tunnel = AsyncMock(return_value=SimpleNamespace(
                url="https://offline-test.tunnel.pinfra.io", tunnel_id="offline-test"))
            viewer = SimpleNamespace(public_readonly=True, token="", interactive=False)
            http = Mock()
            async def get(url, **kwargs):
                self.assertFalse(kwargs.get("headers", {}).get("Authorization"))
                if "/api/status" in url:
                    return SimpleNamespace(status_code=200, json=lambda: {"connected": True, "frame_id": "test"})
                return SimpleNamespace(status_code=200, content=PNG)
            http.get = AsyncMock(side_effect=get)
            http.post = AsyncMock(return_value=SimpleNamespace(status_code=403))
            context = AsyncMock()
            context.__aenter__.return_value = http
            with patch.object(tunnel, "binary", return_value=Path(temp) / "fake-frpc"), \
                 patch.object(tunnel, "config", return_value=Path(temp) / "fake.toml"), \
                 patch("subprocess.Popen", return_value=Mock(poll=Mock(return_value=None))), \
                 patch("httpx.AsyncClient", return_value=context):
                receipt = asyncio.run(tunnel.start(viewer))
            self.assertTrue(receipt["public_png_verified"])
            self.assertFalse(receipt["authenticated_png_verified"])
            self.assertEqual(receipt["unauthenticated_status"], 200)
            self.assertEqual(receipt["access_mode"], "public_readonly")
            self.assertFalse((Path(temp) / "access.json").exists())
            http.post.assert_awaited_once()

    def test_public_start_does_not_read_or_forward_protected_secret(self):
        session = SimpleNamespace(inspection=False, sandbox_id="offline", root=Path("/unused"),
                                  live_frame=Mock(), info={}, persist=Mock())
        viewer = Mock()
        viewer.start_local.return_value = 1234
        viewer.status.return_value = {"connected": True}
        tunnel = Mock(start=AsyncMock(return_value={"access_mode": "public_readonly"}))
        with patch.dict("os.environ", {"DEMOCART_VIEWER_TOKEN": "not-read-for-public"}), \
             patch("amazon_improved_task_001.integrations.live_viewer.LiveViewer", return_value=viewer) as factory, \
             patch("amazon_improved_task_001.integrations.viewer_tunnel.ViewerTunnel", return_value=tunnel):
            asyncio.run(start_viewer(session, public_readonly=True))
        self.assertIsNone(factory.call_args.kwargs["access_token"])
        self.assertTrue(factory.call_args.kwargs["public_readonly"])


if __name__ == "__main__":
    unittest.main()
