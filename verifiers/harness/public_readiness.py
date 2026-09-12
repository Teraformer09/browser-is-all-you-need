"""Bounded, unscored public viewer running entirely inside a Prime VM.

The controller uploads only an ephemeral tunnel binding, never its Prime API key.
No task action or model call is performed by this entry point.
"""
import argparse
import json
import stat
import subprocess
import time
import tomllib
from pathlib import Path

from amazon_cart_001.harness.hosted_worker import Worker, check_root, write_json
from amazon_cart_001.harness.live_device import capture
from amazon_cart_001.harness.runtime_diagnostics import capture_failure
from amazon_cart_001.integrations.live_viewer import LiveViewer


def validate_hold(seconds):
    if type(seconds) is not int or not 60 <= seconds <= 600:
        raise ValueError("Public preview must last between 60 and 600 seconds")


def validate_proxy(path, port):
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("Tunnel binding must be a private regular file")
    raw = path.read_bytes()
    if len(raw) > 16384:
        raise ValueError("Tunnel binding too large")
    config = tomllib.loads(raw.decode())
    expected = {"serverAddr", "serverPort", "user", "auth", "metadatas", "log", "transport", "proxies"}
    if set(config) != expected or len(config["proxies"]) != 1:
        raise ValueError("Unexpected tunnel configuration")
    proxy = config["proxies"][0]
    if set(proxy) != {"name", "type", "localIP", "localPort", "subdomain"}:
        raise ValueError("Unexpected proxy fields")
    if proxy["type"] != "http" or proxy["localIP"] != "127.0.0.1" or proxy["localPort"] != port:
        raise ValueError("Only the read-only loopback viewer may be exposed")
    if config["auth"].get("method") != "token" or not config["auth"].get("token"):
        raise ValueError("Missing ephemeral tunnel authentication")


def run(root, hold_seconds):
    validate_hold(hold_seconds)
    root.mkdir(parents=True, exist_ok=False)
    private = root / ".viewer-private"
    private.mkdir(mode=0o700)
    binding = private / "frpc.toml"
    worker = Worker(root, inspection=True, rubric_profile="peach_strict_v1", acceleration="software")
    report = {"kind": "prime_public_android_preview", "evaluation": False,
              "model_calls": 0, "benchmark_attempts": 0, "inspection_actions": 0,
              "status": "STARTING", "public_readonly": True, "viewer_location": "prime-vm-sandbox"}
    viewer = process = None
    try:
        worker.boot()
        if worker.env.frames[-1]["errors"]:
            raise RuntimeError("Initial app evidence is invalid")

        def frame():
            receipt = capture(root)
            return receipt, Path(receipt["path"]).read_bytes()

        viewer = LiveViewer(frame, public_readonly=True, interval=5,
                            label="DemoCart · Prime Android · unscored live preview")
        port = viewer.start_local()
        if not viewer.status()["connected"]:
            raise RuntimeError("Fresh Android frame unavailable")
        report.update(status="LISTENING", port=port, episode_root=str(worker.env.root))
        write_json(root / "public-preview.json", report)
        # Download verifies the pinned official frp archive hash. No global cache.
        from prime_tunnel.binary import _download_frpc
        binary = private / "frpc"
        _download_frpc(binary)
        deadline = time.monotonic() + 120
        while not binding.is_file():
            if (root / "stop-preview").exists():
                raise RuntimeError("Preview cancelled before tunnel binding")
            if time.monotonic() >= deadline:
                raise TimeoutError("Public tunnel binding not supplied")
            time.sleep(1)
        validate_proxy(binding, port)
        with (private / "frpc.log").open("wb") as stream:
            process = subprocess.Popen([str(binary), "-c", str(binding)], stdout=stream, stderr=stream)
        expires = time.time() + hold_seconds
        report.update(status="LIVE_PENDING_EXTERNAL_CHECK", expires_at_unix=expires)
        write_json(root / "public-preview.json", report)
        while time.time() < expires:
            if (root / "stop-preview").exists():
                report["stop_requested"] = True
                break
            if process.poll() is not None:
                raise RuntimeError("Public tunnel client stopped")
            time.sleep(min(5, max(0, expires - time.time())))
        report["status"] = "PREVIEW_FINISHED"
    except Exception as exc:
        report.update(status="FAILED", error=type(exc).__name__ + ": " + str(exc))
        try:
            report["diagnostics"] = capture_failure(root, worker.env.device if worker.env else None)
        except Exception as error:
            report["diagnostics_error"] = type(error).__name__
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        binding.unlink(missing_ok=True)
        if viewer is not None:
            try:
                viewer.stop_local()
            except Exception as exc:
                report.update(status="FAILED", viewer_cleanup_error=str(exc))
        try:
            report["export"] = worker.finalize()
            if report["export"]["verdict"]["status"] != "NOT_SCORED":
                report["status"] = "FAILED"
        except Exception as exc:
            report.update(status="FAILED", export_error=type(exc).__name__ + ": " + str(exc))
        write_json(root / "public-preview.json", report)
    print(json.dumps(report), flush=True)
    return 0 if report["status"] == "PREVIEW_FINISHED" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--hold-seconds", type=int, default=600)
    args = parser.parse_args()
    raise SystemExit(run(check_root(args.root), args.hold_seconds))


if __name__ == "__main__":
    main()
