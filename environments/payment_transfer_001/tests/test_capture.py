import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_task_checks import fixture

spec = importlib.util.spec_from_file_location("capture", Path(__file__).parents[1] / "scripts/capture_evidence.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

class CaptureTests(unittest.TestCase):
    def fake_device(self, stale=False, wrong_ui=False, broken_png=False):
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if "query" in args:
                data = fixture()
                if stale and sum("query" in a for a in calls) > 1: data["revision"] = 10
                output = ("Row: 0 snapshot=" + json.dumps(data)).encode()
            elif "screencap" in args:
                output = b"broken" if broken_png else b"\x89PNG\r\n\x1a\n" + bytes(25)
            elif "cat" in args:
                package = "other.app" if wrong_ui else capture.PACKAGE
                output = ('<hierarchy><node package="' + package + '"/></hierarchy>').encode()
            else: output = b""
            return subprocess.CompletedProcess(args, 0, output, b"")
        return run, calls
    def exercise(self, **kwargs):
        fake, calls = self.fake_device(**kwargs)
        with tempfile.TemporaryDirectory() as directory, patch.object(capture.subprocess, "run", side_effect=fake):
            root, result = capture.capture("emulator-test", "test", directory)
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["model_calls"], 0)
            self.assertEqual(manifest["actor_actions"], 0)
            self.assertTrue(any("rm" in call for call in calls))
            return result
    def test_capture(self): self.assertEqual(self.exercise()["status"], "PASS")
    def test_changed_during_capture(self): self.assertEqual(self.exercise(stale=True)["status"], "INVALID")
    def test_other_app_ui(self): self.assertEqual(self.exercise(wrong_ui=True)["status"], "INVALID")
    def test_broken_screenshot(self): self.assertEqual(self.exercise(broken_png=True)["status"], "INVALID")

if __name__ == "__main__": unittest.main()
