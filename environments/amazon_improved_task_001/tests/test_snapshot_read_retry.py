"""Transient provider failures remain explicit evidence, never input retries."""
import copy
import unittest
from unittest.mock import patch
import test_text_readback as fixtures
from amazon_improved_task_001.harness.evidence import digest
from amazon_improved_task_001.harness.peach import TextInputUnconfirmed
from amazon_improved_task_001.verification.strict import evaluate

ERROR = "java.lang.IllegalStateException: Read-only snapshot unavailable"


class TransientDevice(fixtures.ReadbackDevice):
    def __init__(self, failures):
        super().__init__([fixtures.TEXT] * 5)
        self.failures = failures
        self.input_readbacks = []

    def command(self, *args, timeout=30):
        if list(args) == fixtures.QUERY and self.failures:
            self.failures -= 1
            self.commands.append(list(args))
            self.trace.append({"args": list(args), "returncode": 0, "bytes": 0,
                               "sha256": digest(b""), "stderr": ERROR, "phase": self.phase})
            return b""
        return super().command(*args, timeout=timeout)


class SnapshotFixture(fixtures.BoundReadbackFixture):
    def execute(self, action, target):
        super().execute(action, target)
        if action["type"] != "type_text": return
        first = self.input_readbacks[0]
        position = first["trace_index"]
        entry = {"args": fixtures.QUERY, "returncode": 0, "bytes": 0, "sha256": digest(b""),
                 "stderr": ERROR, "phase": self.phase}
        self.trace.insert(position, entry)
        for record in self.input_readbacks: record["trace_index"] += 1
        self.input_readbacks.insert(0, {"stage": "before_dismiss", "trace_index": position,
            "expected": action["text"], "actual": None, "episode_id": None, "confirmed": False,
            "error_code": "PROVIDER_SNAPSHOT_UNAVAILABLE", "raw": b""})


class SnapshotReadRetryTests(unittest.TestCase):
    def test_transient_read_is_retained_then_confirmed(self):
        device = TransientDevice(1)
        with patch("time.sleep"):
            device.confirm_text(fixtures.TEXT, "before_dismiss")
        self.assertEqual([r["confirmed"] for r in device.input_readbacks], [False, True])
        self.assertEqual(device.input_readbacks[0]["error_code"], "PROVIDER_SNAPSHOT_UNAVAILABLE")
        self.assertEqual(device.commands, [fixtures.QUERY, fixtures.QUERY])

    def test_persistent_unavailability_is_bounded(self):
        device = TransientDevice(10)
        with patch("time.sleep"):
            with self.assertRaises(TextInputUnconfirmed):
                device.confirm_text(fixtures.TEXT, "before_dismiss")
        self.assertEqual(len(device.input_readbacks), 5)
        self.assertEqual(device.commands, [fixtures.QUERY] * 5)

    def test_full_task_with_recorded_failed_reads_passes_and_forgery_does_not(self):
        helper = fixtures.TextReadbackAuditTests()
        helper.setUp()
        try:
            original = helper.episode
            helper.episode = lambda: original(SnapshotFixture)
            episode = helper.complete()
            self.assertEqual(episode.finalize()["status"], "PASS")
            context = copy.deepcopy(episode.context)
            record = context["transitions"][0]["input_readbacks"][0]
            context["adb_trace"][record["trace_index"]]["stderr"] = "permission denied"
            self.assertNotEqual(evaluate(context)["status"], "PASS")
        finally:
            helper.doCleanups()
