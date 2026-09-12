"""Live Android viewer: protected inspection or explicitly public read-only display."""
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit, parse_qs


class LiveViewer:
    def __init__(self, capture, control=None, *, interactive=False, label="Prime Android", interval=1.5, access_token=None, test_fixture=False, public_readonly=False, local_readiness=False):
        if type(public_readonly) is not bool:
            raise ValueError("public_readonly must be a boolean")
        if public_readonly and (interactive or control is not None or access_token is not None):
            raise ValueError("Public viewer is read-only and must not receive controls or secrets")
        if type(local_readiness) is not bool:
            raise ValueError("local_readiness must be a boolean")
        if local_readiness and (interactive or control is not None):
            raise ValueError("Local readiness is read-only, not an interactive evaluation")
        self.local_readiness = local_readiness
        self.public_readonly = public_readonly
        if interactive and control is None:
            raise ValueError("Interactive viewer requires an inspection callback")
        self.capture, self.control = capture, control
        self.interactive, self.label, self.interval = interactive, label, interval
        if access_token is not None and (not isinstance(access_token, str) or re.fullmatch(r"[A-Za-z0-9_-]{43,128}", access_token) is None):
            raise ValueError("Viewer access token must be a strong URL-safe secret")
        self.token = "" if public_readonly else access_token or secrets.token_urlsafe(32)
        self.test_fixture = test_fixture is True
        self.lock, self.control_lock = threading.Lock(), threading.Lock()
        self.stop_event = threading.Event()
        self.frame, self.png, self.error = None, None, None
        self.received_at, self.last_control = 0, 0
        self.server = self.thread = self.poller = None
        self.tunnel = None

    def status(self):
        with self.lock:
            age = time.monotonic() - self.received_at if self.frame else None
            return {"label": self.label, "interactive": self.interactive, "test_fixture": self.test_fixture,
                    "connected": bool(self.frame and age <= 10 and not self.error and not self.stop_event.is_set()),
                    "frame_age_seconds": round(age, 1) if age is not None else None,
                    "frame_id": self.frame.get("frame_id") if self.frame else None,
                    "width": self.frame.get("width") if self.frame else None,
                    "height": self.frame.get("height") if self.frame else None,
                    "error": ("Live frame unavailable; retrying" if self.public_readonly and self.error else self.error),
                    "public_readonly": self.public_readonly, "local_readiness": self.local_readiness,
                    "evaluation_control_disabled": not self.interactive}

    def update(self):
        requested_at = time.monotonic()
        try:
            frame, png = self.capture()
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 8 * 1024 * 1024:
                raise ValueError("Invalid live PNG")
            if hashlib.sha256(png).hexdigest() != frame["sha256"]:
                raise ValueError("Live frame hash mismatch")
            with self.lock:
                if self.frame is None or frame["frame_id"] != self.frame["frame_id"]:
                    # Include capture/download latency; replaying the same cached
                    # frame must not make a stale display appear live again.
                    self.received_at = requested_at
                self.frame, self.png, self.error = frame, png, None
        except Exception as exc:
            with self.lock:
                self.error = type(exc).__name__ + ": " + str(exc)[:300]

    def _poll(self):
        while not self.stop_event.wait(self.interval):
            self.update()

    def start_local(self):
        if self.server:
            raise RuntimeError("Viewer already started")
        viewer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Never log access tokens, URLs, or user input.

            def reply(self, code, body, mime="application/json"):
                if not isinstance(body, bytes):
                    body = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
                self.end_headers()
                self.wfile.write(body)

            def authorized(self):
                expected = "Bearer " + viewer.token
                actual = self.headers.get("Authorization", "")
                if not hmac.compare_digest(actual.encode(), expected.encode()):
                    self.reply(401, {"error": "Viewer access token required"})
                    return False
                return True

            def do_GET(self):
                path = urlsplit(self.path).path
                assets = {"/": ("index.html", "text/html; charset=utf-8"),
                          "/viewer.js": ("viewer.js", "text/javascript; charset=utf-8"),
                          "/viewer.css": ("viewer.css", "text/css; charset=utf-8")}
                if path in assets:
                    name, mime = assets[path]
                    return self.reply(200, files("amazon_cart_001").joinpath("viewer", name).read_bytes(), mime)
                if path == "/api/viewer-mode":
                    return self.reply(200, {"public_readonly": viewer.public_readonly,
                                            "authentication_required": not viewer.public_readonly})
                if viewer.public_readonly:
                    if path not in {"/api/status", "/api/frame"}:
                        return self.reply(404, {"error": "Not found"})
                elif not self.authorized():
                    return
                if path == "/api/status":
                    return self.reply(200, viewer.status())
                if path == "/api/frame":
                    requested = parse_qs(urlsplit(self.path).query).get("frame_id", [None])[0]
                    with viewer.lock:
                        if requested is not None and (viewer.frame is None or requested != viewer.frame["frame_id"]):
                            return self.reply(409, {"error": "Frame changed; refresh metadata"})
                        png = viewer.png
                    return self.reply(200, png, "image/png") if png else self.reply(503, {"error": "No frame yet"})
                self.reply(404, {"error": "Not found"})

            def do_POST(self):
                if viewer.public_readonly:
                    return self.reply(403, {"error": "READ_ONLY_EVALUATION: public viewers cannot send input"})
                if not self.authorized():
                    return
                if urlsplit(self.path).path != "/api/control":
                    return self.reply(404, {"error": "Not found"})
                if not viewer.interactive:
                    return self.reply(403, {"error": "READ_ONLY_EVALUATION: human control is disabled"})
                if self.headers.get("Content-Type") != "application/json":
                    return self.reply(415, {"error": "JSON required"})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2048:
                        return self.reply(413, {"error": "Invalid body size"})
                    if not viewer.control_lock.acquire(blocking=False):
                        return self.reply(429, {"error": "Wait for the current control"})
                    try:
                        if not viewer.status()["connected"]:
                            return self.reply(409, {"error": "No fresh live frame"})
                        if time.monotonic() - viewer.last_control < 0.25:
                            return self.reply(429, {"error": "Control rate limit"})
                        viewer.last_control = time.monotonic()
                        result = viewer.control(json.loads(self.rfile.read(length)))
                        return self.reply(200, result)
                    finally:
                        viewer.control_lock.release()
                except (ValueError, KeyError, TypeError) as exc:
                    self.reply(400, {"error": str(exc)[:300]})
                except Exception:
                    self.reply(503, {"error": "Control transport failed; refresh before retrying"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="democart-viewer-http")
        self.thread.start()
        self.update()
        self.poller = threading.Thread(target=self._poll, daemon=True, name="democart-viewer-capture")
        self.poller.start()
        return self.server.server_port

    def stop_local(self):
        self.stop_event.set()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.poller:
            self.poller.join(timeout=65)
            if self.poller.is_alive():
                raise RuntimeError("Live capture did not stop; inspect before teardown")
        if self.thread:
            self.thread.join(timeout=5)
        if not self.public_readonly:
            self.token = secrets.token_urlsafe(32)  # Revoke old capability immediately.


