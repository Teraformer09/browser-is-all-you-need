"""One unscored software-CPU boot/UI/media check. Never calls a model."""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from amazon_cart_001.harness.hosted_worker import Worker, check_root, write_json
from amazon_cart_001.harness.live_device import capture
from amazon_cart_001.harness.runtime_diagnostics import capture_failure
from amazon_cart_001.integrations.live_viewer import LiveViewer


def run(root):
    root.mkdir(parents=True, exist_ok=False)
    worker = Worker(root, inspection=True, rubric_profile="peach_strict_v1", acceleration="software")
    report = {"kind": "prime_software_runtime_readiness", "evaluation": False, "model_calls": 0,
              "benchmark_attempts": 0, "inspection_actions": 0, "status": "STARTING"}
    viewer = None
    started = time.monotonic()
    try:
        worker.boot()
        report["boot_and_capture_seconds"] = round(time.monotonic() - started, 3)
        if worker.env.frames[-1]["errors"]:
            raise RuntimeError("INITIAL_EVIDENCE_ERRORS: " + str(worker.env.frames[-1]["errors"]))
        def frame():
            receipt = capture(root)
            return receipt, Path(receipt["path"]).read_bytes()
        viewer = LiveViewer(frame, public_readonly=True, label="Prime software Android · readiness only", interval=5)
        port = viewer.start_local()
        url = "http://127.0.0.1:" + str(port)
        status = json.load(urllib.request.urlopen(url + "/api/status", timeout=30))
        if not status["connected"]:
            raise RuntimeError("Live Android frame unavailable")
        png = urllib.request.urlopen(url + "/api/frame?frame_id=" + status["frame_id"], timeout=30).read()
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("Viewer did not serve an actual PNG")
        report["live_viewer"] = {"checked_inside_prime_vm": True, "public_url_created": False,
                                 "connected": True, "initial_png_sha256": hashlib.sha256(png).hexdigest()}
        worker.env.step(json.dumps({"type": "tap_element", "element_id": "cart_button"}))
        report["inspection_actions"] = 1
        receipt = worker.env.transitions[-1]["receipt"]
        report["cart_tap_receipt"] = receipt
        if not receipt["accepted"] or worker.env.frames[-1]["state"]["page"] != "cart":
            raise RuntimeError("CART_NAVIGATION_NOT_CONFIRMED")
        viewer.update()
        report["screenshots"] = [f["artifacts"]["screen.png"] for f in worker.env.frames]
        report["episode_root"] = str(worker.env.root)
        report["status"] = "READY"
    except Exception as exc:
        report.update(status="FAILED", error=type(exc).__name__ + ": " + str(exc))
        try:
            report["diagnostics"] = capture_failure(root, worker.env.device if worker.env else None)
        except Exception as diagnostic_error:
            report["diagnostics_error"] = str(diagnostic_error)
    finally:
        if viewer is not None:
            try:
                viewer.stop_local()
            except Exception as exc:
                report.update(status="FAILED", viewer_cleanup_error=str(exc))
        try:
            final = worker.finalize()
            report["export"] = final
            if final["verdict"]["status"] != "NOT_SCORED":
                report.update(status="FAILED", recording_or_pipeline_error=final["verdict"])
        except Exception as exc:
            report.update(status="FAILED", export_error=type(exc).__name__ + ": " + str(exc))
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(root / "readiness.json", report)
    print(json.dumps(report), flush=True)
    return 0 if report["status"] == "READY" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    raise SystemExit(run(check_root(args.root)))


if __name__ == "__main__":
    main()
