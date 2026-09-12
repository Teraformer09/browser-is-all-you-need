"""Bounded, read-only failure evidence; never substitutes for valid task frames."""
import json
import subprocess
from pathlib import Path

from amazon_cart_001.harness.evidence import digest, stamp


def capture_failure(root, device=None):
    directory = Path(root) / "diagnostics"
    directory.mkdir(exist_ok=True)
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    report = {"kind": "runtime_failure_diagnostics", "scored": False, "at": stamp(),
              "artifacts": {}, "errors": [], "commands": []}
    # Every command is inspection-only. The UI dump is a private temporary file,
    # removed after reading; no app inputs, dismissal, reset, or retry is sent.
    remote_ui = "/data/local/tmp/democart-readiness-failure.xml"
    commands = [
        ("window.log", ["shell", "dumpsys", "window", "windows"], 10),
        ("activity.log", ["shell", "dumpsys", "activity", "activities"], 10),
        ("logcat.log", ["shell", "logcat", "-d", "-t", "250"], 10),
        ("screen.png", ["exec-out", "screencap", "-p"], 30),
        ("ui-dump.log", ["shell", "uiautomator", "dump", remote_ui], 15),
        ("ui.xml", ["shell", "cat", remote_ui], 5),
        ("ui-cleanup.log", ["shell", "rm", "-f", remote_ui], 5),
    ]
    for name, arguments, timeout in commands:
        entry = {"arguments": arguments, "timeout_seconds": timeout}
        try:
            result = subprocess.run(["adb", "-s", "emulator-5556", *arguments],
                                    capture_output=True, timeout=timeout)
            entry.update(returncode=result.returncode,
                         stderr=result.stderr.decode(errors="replace")[:4000])
            data = result.stdout
            if result.returncode != 0:
                raise RuntimeError("Diagnostic command returned " + str(result.returncode))
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Diagnostic output exceeds export bound")
            if name == "screen.png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Diagnostic screen is not a PNG")
            (directory / name).write_bytes(data)
            report["artifacts"][name] = {"path": "diagnostics/" + name,
                                        "bytes": len(data), "sha256": digest(data)}
        except Exception as exc:
            entry["error"] = type(exc).__name__ + ": " + str(exc)
            report["errors"].append({"file": name, "error": entry["error"]})
        report["commands"].append(entry)
    if device is not None:
        data = json.dumps(device.trace, ensure_ascii=True).encode()
        (directory / "device-trace.json").write_bytes(data)
        report["artifacts"]["device-trace.json"] = {
            "path": "diagnostics/device-trace.json", "bytes": len(data), "sha256": digest(data)}
    manifest_path.write_text(json.dumps(report, indent=2) + "\n")
    return report

