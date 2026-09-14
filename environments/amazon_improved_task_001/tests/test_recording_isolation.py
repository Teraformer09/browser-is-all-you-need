"""Video housekeeping must never enter concurrent actor action receipts."""
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from amazon_improved_task_001.harness.device import Device
from amazon_improved_task_001.harness.recording import ScreenRecording


class RecordingIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.actor = Device("emulator-5556", "/scoped/adb")
        self.actor.phase = "action"
        self.recorder = ScreenRecording(self.actor, self.temp.name, "peach_" + "a" * 32, "ffmpeg")

    def test_recording_has_separate_trace_and_preserves_endpoint(self):
        self.assertIsNot(self.recorder.device, self.actor)
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, b"video", b"")) as run:
            self.recorder.device.command("exec-out", "cat", "/sdcard/segment.mp4")
        self.assertEqual(run.call_args.args[0][:3], ["/scoped/adb", "-s", "emulator-5556"])
        self.assertEqual(self.actor.trace, [])
        receipt = self.recorder.receipt()
        self.assertEqual(receipt["command_trace_scope"], "recording_only")
        self.assertEqual(receipt["command_trace"][0]["phase"], "recording")

    def test_video_rotation_during_action_does_not_contaminate_trace(self):
        entered, release = threading.Event(), threading.Event()
        errors = []
        def execute(args, **kwargs):
            if args[-1] == "actor.xml":
                entered.set()
                if not release.wait(2): raise RuntimeError("test synchronization timeout")
            return subprocess.CompletedProcess(args, 0, b"", b"")
        def actor_action():
            try: self.actor.command("shell", "uiautomator", "dump", "actor.xml")
            except Exception as error: errors.append(error)
        with patch("subprocess.run", side_effect=execute):
            thread = threading.Thread(target=actor_action)
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                self.recorder.device.command("exec-out", "cat", "/sdcard/segment.mp4")
                self.recorder.device.command("shell", "rm", "-f", "/sdcard/segment.mp4")
            finally:
                release.set()
                thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(self.actor.trace), 1)
        self.assertEqual(self.actor.trace[0]["args"], ["shell", "uiautomator", "dump", "actor.xml"])
        self.assertEqual(len(self.recorder.receipt()["command_trace"]), 2)

    def test_recorder_failure_is_kept_in_recording_receipt(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, b"", b"read failed")):
            with self.assertRaises(subprocess.CalledProcessError):
                self.recorder.device.command("exec-out", "cat", "/sdcard/segment.mp4")
        self.assertEqual(self.actor.trace, [])
        self.assertIn("error", self.recorder.receipt()["command_trace"][0])
