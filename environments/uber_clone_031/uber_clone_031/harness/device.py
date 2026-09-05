from __future__ import annotations
import hashlib
import json
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from uuid import uuid4
from uber_clone_031.harness.backend.adb_device import AdbDevice, UiNode
from uber_clone_031.harness.backend.apk_env import ApkAction, DummyApkEnv
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.harness.backend.env import StepResult
from uber_clone_031.verification.records import parse_state, verify

class TracedAdbDevice(AdbDevice):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trace = []
        self.phase = "setup"
        self.observation_freshness = {}

    def adb(self, *args, check=True, timeout_s=None):
        start = time.monotonic()
        event = {"time": datetime.now(timezone.utc).isoformat(), "args": list(args), "check": check, "phase": self.phase}
        try:
            result = super().adb(*args, check=check, timeout_s=timeout_s)
            event.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            return result
        except Exception as exc:
            event.update(error=f"{type(exc).__name__}: {exc}",
                         stdout=str(getattr(exc, "stdout", "") or ""),
                         stderr=str(getattr(exc, "stderr", "") or ""))
            raise
        finally:
            event["duration_ms"] = round((time.monotonic() - start) * 1000, 2)
            self.trace.append(event)

    def dump_ui(self):
        # Unique paths prevent a failed dump from reusing an old window.xml.
        path = f"/sdcard/uber031-ui-{uuid4().hex}.xml"
        self.observation_freshness = {"fresh": False, "fallback_used": False, "path": path}
        try:
            self.adb("shell", "uiautomator", "dump", path, timeout_s=15)
            xml = self.adb("exec-out", "cat", path, timeout_s=8).stdout
            if ET.fromstring(xml).tag != "hierarchy":
                raise ValueError("UI dump is not a hierarchy")
            self.observation_freshness.update(fresh=True, captured_at=datetime.now(timezone.utc).isoformat(),
                                             sha256=hashlib.sha256(xml.encode()).hexdigest())
            return xml
        except Exception as exc:
            self.observation_freshness["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.adb("shell", "rm", "-f", path, check=False, timeout_s=8)

    def find_resource(self, resource_name):
        # No hidden swipes: scrolling is an explicit, budgeted policy action.
        resource_id = f"{self.package}:id/{resource_name}"
        for node in ET.fromstring(self.dump_ui()).iter("node"):
            if node.get("resource-id") == resource_id and node.get("enabled") == "true":
                return UiNode(resource_id, node.get("text", ""), self._parse_bounds(node.get("bounds", "")),
                              node.get("focused") == "true")
        raise LookupError(f"Target not visible/enabled: {resource_name}; scroll explicitly if needed")

    def _escape_input_text(self, text):
        # adb shell joins arguments; quote remote text so it cannot become shell code.
        return shlex.quote(text.replace("%", "%25").replace(" ", "%s"))

    def input_resource(self, resource_name, text):
        self.click_resource(resource_name)
        if not self.find_resource(resource_name).focused:
            raise RuntimeError(f"Input did not acquire focus: {resource_name}")
        # Android input supports a real Ctrl+A key combination, not KEYCODE_CTRL_A.
        self.adb("shell", "input", "keycombination", "113", "29")
        self.adb("shell", "input", "keyevent", "KEYCODE_DEL")
        if text:
            self.adb("shell", "input", "text", self._escape_input_text(text))
        time.sleep(0.3)

    def read_shared_prefs(self):
        result = self.adb("shell", "run-as", self.package, "cat", "shared_prefs/dummy_state.xml")
        if not parse_state(result.stdout):
            raise ValueError("App preferences are missing or malformed; no UI-state fallback")
        return result.stdout

    def capture_png(self):
        command = [self.adb_path] + (["-s", self.serial] if self.serial else []) + ["exec-out", "screencap", "-p"]
        start = time.monotonic()
        event = {"time": datetime.now(timezone.utc).isoformat(), "args": ["exec-out", "screencap", "-p"], "phase": self.phase}
        try:
            result = subprocess.run(command, check=True, capture_output=True, timeout=25)
            event.update(returncode=result.returncode, bytes=len(result.stdout),
                         sha256=hashlib.sha256(result.stdout).hexdigest(), stderr=result.stderr.decode(errors="replace"))
            return result.stdout
        except Exception as exc:
            event["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            event["duration_ms"] = round((time.monotonic() - start) * 1000, 2)
            self.trace.append(event)

    def read_runtime_probe(self):
        output = self.adb("shell", "content", "query", "--uri",
                          "content://com.primeintellect.dummyrl.verifier/state").stdout
        if "snapshot=" not in output:
            raise ValueError("Read-only runtime probe did not return a snapshot")
        result = json.loads(output.split("snapshot=", 1)[1].strip())
        if not isinstance(result, dict):
            raise ValueError("Runtime probe must return an object")
        return result

    def read_mutations(self):
        output = self.adb("shell", "run-as", self.package, "cat", "files/ride_mutations.jsonl").stdout
        events = [json.loads(line) for line in output.splitlines() if line.strip()]
        if not events or any(not isinstance(e, dict) for e in events):
            raise ValueError("App mutation journal is unavailable")
        return events

    def installed_apk(self):
        paths = self.adb("shell", "pm", "path", self.package).stdout.splitlines()
        path = next((line.removeprefix("package:").strip() for line in paths if line.endswith("/base.apk")), None)
        if not path:
            raise RuntimeError("Installed base APK not found")
        digest = self.adb("shell", "sha256sum", path).stdout.split()[0]
        if len(digest) != 64:
            raise ValueError("Invalid installed APK hash")
        return {"package": self.package, "path": path, "sha256": digest}
