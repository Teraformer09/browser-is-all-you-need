"""Failure diagnostics cannot convert a failed capture into a task pass."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

from amazon_improved_task_001.harness.hosted_worker import Worker
from amazon_improved_task_001.harness.runtime_diagnostics import capture_failure


class RuntimeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def result(self, args, **kwargs):
        data = b"\x89PNG\r\n\x1a\n" + bytes(32) if "screencap" in args else b"diagnostic"
        return SimpleNamespace(returncode=0, stdout=data, stderr=b"")

    def test_read_only_diagnostics_are_separate_and_idempotent(self):
        with patch("subprocess.run", side_effect=self.result) as run:
            report = capture_failure(self.root, SimpleNamespace(trace=[{"phase": "setup"}]))
            self.assertEqual(report, capture_failure(self.root))
        self.assertEqual(run.call_count, 7)
        self.assertFalse(report["scored"])
        self.assertEqual(report["errors"], [])
        self.assertFalse((self.root / "frames").exists())
        self.assertIn("device-trace.json", report["artifacts"])
        self.assertLessEqual(sum(call.kwargs["timeout"] for call in run.call_args_list), 85)
        for call in run.call_args_list:
            if "screencap" in call.args[0]:
                self.assertEqual(call.kwargs["timeout"], 30)
            else:
                self.assertLessEqual(call.kwargs["timeout"], 15)
            self.assertNotIn("input", call.args[0])
            self.assertNotIn("start", call.args[0])

    def test_timeout_does_not_hide_other_evidence(self):
        def result(args, **kwargs):
            if "window" in args:
                raise subprocess.TimeoutExpired(args, kwargs["timeout"])
            return self.result(args, **kwargs)
        with patch("subprocess.run", side_effect=result):
            report = capture_failure(self.root)
        self.assertEqual(report["errors"][0]["file"], "window.log")
        self.assertIn("screen.png", report["artifacts"])
        self.assertEqual(len(report["commands"]), 7)

    def test_invalid_png_is_never_exported_as_screenshot(self):
        result = SimpleNamespace(returncode=0, stdout=b"not a png", stderr=b"")
        with patch("subprocess.run", return_value=result):
            report = capture_failure(self.root)
        self.assertNotIn("screen.png", report["artifacts"])
        self.assertFalse((self.root / "diagnostics/screen.png").exists())

    def test_worker_exports_failure_evidence_without_success(self):
        with patch("subprocess.run", side_effect=self.result):
            capture_failure(self.root)
        final = Worker(self.root, inspection=True).finalize()
        self.assertEqual(final["verdict"]["status"], "INVALID")
        with ZipFile(final["archive"]["path"]) as archive:
            self.assertIn("diagnostics/screen.png", archive.namelist())
            report = json.loads(archive.read("diagnostics/manifest.json"))
            self.assertFalse(report["scored"])
