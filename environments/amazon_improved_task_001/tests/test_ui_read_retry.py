"""Retry only explicit empty-root reads; never replay an action."""
import copy
import unittest
from unittest.mock import patch
import test_text_readback as fixtures
from amazon_improved_task_001.harness.peach import PeachDevice
from amazon_improved_task_001.verification.strict import evaluate

ERROR = "ERROR: null root node returned by UiTestAutomationBridge."


class EmptyRootDevice(PeachDevice):
    def __init__(self, failures, error=ERROR):
        super().__init__("FAKE")
        self.failures, self.message, self.dumps = failures, error, 0

    def command(self, *args, timeout=30):
        raw, stderr = b"", ""
        if args[:3] == ("shell", "uiautomator", "dump"):
            self.dumps += 1
            if self.dumps <= self.failures: stderr = self.message
            else: raw = b"UI hierarchy dumped to: " + args[3].encode()
        elif args[:2] == ("exec-out", "cat"):
            raw = b"<hierarchy/>"
        self.trace.append({"args": list(args), "stderr": stderr, "returncode": 0})
        return raw


class RetryFixture(fixtures.BoundReadbackFixture):
    def ui(self):
        if self.phase == "action":
            remote = "/sdcard/peach-ui-" + "c" * 32 + ".xml"
            self.trace_entry(["shell", "uiautomator", "dump", remote], b"")
            self.trace[-1]["stderr"] = ERROR
            self.trace_entry(["shell", "rm", "-f", remote], b"")
        return super().ui()


class UIReadRetryTests(unittest.TestCase):
    def test_empty_root_then_success(self):
        device = EmptyRootDevice(1)
        self.assertEqual(device.ui(), b"<hierarchy/>")
        self.assertEqual(device.dumps, 2)
        self.assertEqual(sum(t["args"][:3] == ["shell", "rm", "-f"] for t in device.trace), 2)
        self.assertFalse(any(t["args"][:2] == ["shell", "input"] for t in device.trace))

    def test_three_empty_roots_stop(self):
        device = EmptyRootDevice(10)
        with self.assertRaisesRegex(RuntimeError, "UI dump"):
            device.ui()
        self.assertEqual(device.dumps, 3)

    def test_unrecognized_error_is_not_retried(self):
        device = EmptyRootDevice(10, "permission denied")
        with self.assertRaises(RuntimeError):
            device.ui()
        self.assertEqual(device.dumps, 1)

    def complete(self):
        helper = fixtures.TextReadbackAuditTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        original = helper.episode
        helper.episode = lambda: original(RetryFixture)
        return helper.complete()

    def test_bound_empty_root_retry_is_auditable(self):
        episode = self.complete()
        self.assertEqual(episode.finalize()["status"], "PASS")

    def test_changed_retry_command_cannot_pass(self):
        episode = self.complete()
        context = copy.deepcopy(episode.context)
        start = context["transitions"][0]["trace_start"]
        context["adb_trace"][start]["args"] = ["shell", "input", "tap", "1", "1"]
        self.assertNotEqual(evaluate(context)["status"], "PASS")
