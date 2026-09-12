"""Prime HTTPS relay with a private, run-local frpc configuration.

Only public URL/health receipts are reportable. The viewer token and tunnel
transport secrets stay in 0600 files and are never added to evaluation samples.
"""
import asyncio
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
    except BaseException:
        # fdopen takes ownership of the descriptor.
        raise


class ViewerTunnel:
    def __init__(self, port, root):
        from prime_tunnel.core.client import TunnelClient
        self.port, self.root = port, Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.client, self.info, self.process = TunnelClient(), None, None
        self.receipt = None

    def binary(self):
        # The pinned SDK verifies the official frp release archive SHA-256.
        # Avoid get_frpc_path(), which writes to ~/.prime rather than this run.
        from prime_tunnel.binary import _download_frpc
        path = self.root / "frpc"
        digest_file = self.root / "frpc.sha256"
        if not path.exists():
            _download_frpc(path)
            digest_file.write_text(hashlib.sha256(path.read_bytes()).hexdigest())
        if not digest_file.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest_file.read_text():
            raise RuntimeError("Tunnel binary integrity check failed")
        return path

    def config(self):
        value = self.info
        quote = json.dumps
        content = "\n".join([
            "serverAddr = " + quote(value.server_host), "serverPort = " + str(value.server_port),
            "user = " + quote(value.tunnel_id), 'auth.method = "token"',
            "auth.token = " + quote(value.frp_token),
            "metadatas.binding_secret = " + quote(value.binding_secret),
            'log.to = "console"', 'log.level = "error"', 'transport.tcpMux = true',
            "[[proxies]]", "name = " + quote(value.tunnel_id), 'type = "http"',
            'localIP = "127.0.0.1"', "localPort = " + str(self.port),
            "subdomain = " + quote(value.tunnel_id), ""])
        path = self.root / "frpc.toml"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        return path

    async def start(self, viewer):
        import httpx
        try:
            binary = await asyncio.to_thread(self.binary)
            self.info = await self.client.create_tunnel(local_port=self.port, name="DemoCart live Android",
                                                        labels=["democart-live", "session-scoped"])
            url = urlsplit(self.info.url)
            if url.scheme != "https" or not url.hostname or not url.hostname.endswith(".tunnel.pinfra.io"):
                raise RuntimeError("Unexpected Prime tunnel URL")
            config = self.config()
            with (self.root / "frpc.log").open("wb") as log:
                self.process = subprocess.Popen([str(binary), "-c", str(config)], stdout=log, stderr=log)
            deadline = time.monotonic() + 45
            async with httpx.AsyncClient(timeout=6, follow_redirects=False) as client:
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        raise RuntimeError("Prime tunnel client exited; private diagnostics retained")
                    try:
                        headers = {} if viewer.public_readonly else {"Authorization": "Bearer " + viewer.token}
                        denied = await client.get(self.info.url + "/api/status")
                        response = denied if viewer.public_readonly else await client.get(self.info.url + "/api/status", headers=headers)
                        expected_unauthenticated = 200 if viewer.public_readonly else 401
                        if denied.status_code == expected_unauthenticated and response.status_code == 200 and response.json().get("connected") is True:
                            frame_id = response.json()["frame_id"]
                            frame = await client.get(self.info.url + "/api/frame?frame_id=" + frame_id,
                                                      headers=headers)
                            if frame.status_code == 200 and frame.content.startswith(b"\x89PNG\r\n\x1a\n"):
                                if viewer.public_readonly:
                                    blocked = await client.post(self.info.url + "/api/control", json={})
                                    if blocked.status_code != 403:
                                        raise RuntimeError("Public viewer input was not blocked")
                                self.receipt = {"url": self.info.url, "tunnel_id": self.info.tunnel_id,
                                    "https_verified": True, "unauthenticated_status": expected_unauthenticated,
                                    "authenticated_png_verified": not viewer.public_readonly,
                                    "public_png_verified": viewer.public_readonly, "verified_at": time.time(),
                                    "access_mode": "public_readonly" if viewer.public_readonly else "token_protected",
                                    "interactive": viewer.interactive}
                                if not viewer.public_readonly:
                                    private_json(self.root / "access.json", {
                                        "url": self.info.url + "/#token=" + viewer.token,
                                        "token": viewer.token, "note": "Private, expires with this session"})
                                return self.receipt
                    except (httpx.HTTPError, ValueError, KeyError):
                        pass
                    await asyncio.sleep(1)
            raise RuntimeError("Live HTTPS and authentication could not be verified")
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    await asyncio.to_thread(self.process.wait, 5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    await asyncio.to_thread(self.process.wait, 3)
            if self.info is not None:
                await self.client.delete_tunnel(self.info.tunnel_id)
                self.info = None
        finally:
            (self.root / "frpc.toml").unlink(missing_ok=True)
            (self.root / "access.json").unlink(missing_ok=True)
            await self.client.close()


async def start_viewer(session, *, interactive=False, public_readonly=False):
    from amazon_cart_001.integrations.live_viewer import LiveViewer
    if bool(session.inspection) != bool(interactive):
        raise ValueError("Viewer control mode must match the worker's immutable run mode")
    viewer = LiveViewer(session.live_frame, session.live_control if interactive else None,
                        interactive=interactive, label="DemoCart · Prime Android" if public_readonly else "Prime VM · " + session.sandbox_id,
                        access_token=None if public_readonly else os.environ.get("DEMOCART_VIEWER_TOKEN"),
                        public_readonly=public_readonly)
    try:
        port = await asyncio.to_thread(viewer.start_local)
        deadline = time.monotonic() + 30
        while not viewer.status()["connected"] and time.monotonic() < deadline:
            await asyncio.sleep(0.5)
        if not viewer.status()["connected"]:
            raise RuntimeError("No verified Android live frame after bounded retry; refusing to publish a placeholder URL")
        viewer.tunnel = ViewerTunnel(port, session.root / ".viewer-private")
        session.info["live_viewer"] = await viewer.tunnel.start(viewer)
        session.persist()
        return viewer
    except BaseException:
        try:
            if viewer.tunnel:
                await viewer.tunnel.stop()
        finally:
            await asyncio.to_thread(viewer.stop_local)
        raise


async def stop_viewer(viewer):
    if viewer is None:
        return
    try:
        await asyncio.to_thread(viewer.stop_local)
    finally:
        if viewer.tunnel:
            await viewer.tunnel.stop()

