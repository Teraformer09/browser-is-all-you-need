from payment_transfer_001.harness.evidence import stamp, save, digest, nodes, prefs_snapshot
import csv
import hashlib
import io
import json
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET
from payment_transfer_001.harness.actions import PACKAGE


class Device:
    def __init__(self, serial, adb="adb"):
        if not serial:
            raise ValueError("An explicit ADB serial is required")
        self.serial, self.adb = serial, adb
        self.trace, self.phase = [], "setup"

    def command(self, *args, timeout=30):
        start = time.monotonic()
        entry = {"args": list(args), "phase": self.phase, "time": stamp()}
        try:
            result = subprocess.run([self.adb, "-s", self.serial, *args],
                                    capture_output=True, timeout=timeout)
            entry.update(returncode=result.returncode, bytes=len(result.stdout),
                         sha256=digest(result.stdout), stderr=result.stderr.decode(errors="replace")[:2000])
            result.check_returncode()
            return result.stdout
        except Exception as exc:
            entry["error"] = type(exc).__name__ + ": " + str(exc)
            raise
        finally:
            entry["duration_ms"] = round((time.monotonic()-start)*1000, 2)
            self.trace.append(entry)

    def runtime(self):
        raw = self.command("shell", "content", "query", "--uri",
                           "content://" + PACKAGE + ".verifier/state").decode()
        if "snapshot=" not in raw:
            raise ValueError("Live payment state unavailable")
        return json.loads(raw.split("snapshot=", 1)[1].strip())

    def ui(self):
        temp = "/sdcard/payment-eval-" + uuid4().hex + ".xml"
        try:
            self.command("shell", "uiautomator", "dump", temp, timeout=20)
            data = self.command("exec-out", "cat", temp)
            if not nodes(data):
                raise ValueError("Payment app is not visible")
            return data
        finally:
            self.command("shell", "rm", "-f", temp)

    def installed(self, apk):
        paths = self.command("shell", "pm", "path", PACKAGE).decode().splitlines()
        if len(paths) != 1 or not paths[0].startswith("package:/data/app/") or not paths[0].endswith("/base.apk"):
            raise ValueError("Installed APK location is unexpected")
        path = paths[0][8:]
        actual = self.command("shell", "sha256sum", path).decode().split()[0]
        expected = digest(Path(apk).read_bytes())
        if actual != expected:
            raise ValueError("Installed APK does not match the selected build")
        return {"package": PACKAGE, "path": path, "sha256": actual, "expected_sha256": expected}

    def start(self, episode):
        output = self.command("shell", "am", "start", "-S", "-W", "-n", PACKAGE + "/.MainActivity",
                              "--es", "episode_id", episode).decode()
        if "Status: ok" not in output:
            raise RuntimeError("App launch failed: " + output)
        time.sleep(1)

    def capture(self, root, index, episode):
        self.phase = "observation"
        base = Path(root) / "frames" / f"{index:03d}"
        base.mkdir(parents=True, exist_ok=False)
        artifacts = {}
        frame = {"index": index, "episode_id": episode, "time": stamp(), "artifacts": artifacts, "errors": []}
        def write(name, data):
            path = base / name
            path.write_bytes(data)
            artifacts[name] = {"path": str(path.relative_to(root)), "sha256": digest(data)}
        try:
            before = self.runtime()
            write("runtime_before.json", json.dumps(before).encode())
            xml = self.ui()
            write("ui.xml", xml)
            png = self.command("exec-out", "screencap", "-p")
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) < 33:
                raise ValueError("Invalid PNG capture")
            write("screen.png", png)
            persisted = self.command("shell", "run-as", PACKAGE, "cat", "shared_prefs/payment_state.xml")
            write("preferences.xml", persisted)
            after = self.runtime()
            write("runtime.json", json.dumps(after).encode())
            frame["ui"] = nodes(xml)
            frame["stable"] = before == after == prefs_snapshot(persisted)
            if after.get("episode_id") != episode or not frame["stable"]:
                raise ValueError("Episode identity changed or capture was not stable")
            frame["state"] = after
            write("journal.json", json.dumps(after["events"]).encode())
            # OCR is an optional evidence channel: absence is INVALID, never a fabricated vote.
            if shutil.which("tesseract"):
                try:
                    result = subprocess.run(["tesseract", str(base / "screen.png"), "stdout", "--psm", "6", "tsv"],
                                            capture_output=True, text=True, timeout=30, check=True)
                    words = [r for r in csv.DictReader(io.StringIO(result.stdout), delimiter="\t") if r.get("text", "").strip()]
                    write("ocr.json", json.dumps({"source_sha256": digest(png), "engine": "tesseract",
                         "words": words, "text": " ".join(w["text"] for w in words)}).encode())
                except Exception as exc:
                    frame["ocr_unavailable"] = type(exc).__name__ + ": " + str(exc)
            else:
                frame["ocr_unavailable"] = "tesseract executable is not installed"
        except Exception as exc:
            frame["errors"].append(type(exc).__name__ + ": " + str(exc))
        save(base / "frame.json", frame)
        return frame

    def execute(self, action, target=None):
        kind = action["type"]
        if kind in {"tap_element", "type_text"}:
            l, t, r, b = target["bounds"]
            self.command("shell", "input", "tap", str((l+r)//2), str((t+b)//2))
            if kind == "type_text":
                self.command("shell", "input", "keycombination", "113", "29")
                self.command("shell", "input", "keyevent", "KEYCODE_DEL")
                if action["text"]:
                    self.command("shell", "input", "text", shlex.quote(action["text"].replace(" ", "%s")))
        elif kind == "press_back":
            self.command("shell", "input", "keyevent", "KEYCODE_BACK")
        elif kind == "swipe":
            self.command("shell", "input", "swipe", *[str(action[k]) for k in ("x1", "y1", "x2", "y2", "duration_ms")])
        elif kind == "wait":
            time.sleep(0.5)
        time.sleep(0.4)
