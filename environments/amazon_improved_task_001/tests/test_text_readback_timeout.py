"""Software-emulator latency regression; virtual time, no device calls."""
import unittest
from unittest.mock import patch
from test_text_readback import ReadbackDevice, QUERY, TEXT
from amazon_improved_task_001.harness.peach import TextInputUnconfirmed


class SlowReadback(ReadbackDevice):
    def __init__(self, drafts, clock):
        super().__init__(drafts)
        self.clock = clock
        self.timeouts = []
        self.input_readbacks = []

    def command(self, *args, timeout=30):
        if list(args) == QUERY:
            self.timeouts.append(timeout)
            self.clock[0] += min(18.3, timeout)
            if timeout < 18.3:
                raise TimeoutError("provider deadline")
        return super().command(*args, timeout=timeout)


class TextReadbackTimeoutTests(unittest.TestCase):
    def test_observed_healthy_provider_latency_is_allowed(self):
        clock = [0.0]
        device = SlowReadback([TEXT, TEXT], clock)
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            device.confirm_text(TEXT, "before_dismiss")
            device.confirm_text(TEXT, "after_dismiss")
        self.assertEqual(device.timeouts, [30, 30])
        self.assertTrue(all(r["confirmed"] for r in device.input_readbacks))
        self.assertEqual(device.commands, [QUERY, QUERY])

    def test_slow_incomplete_state_stays_within_stage_deadline(self):
        clock = [0.0]
        device = SlowReadback(["incomplete"] * 5, clock)
        def sleep(seconds):
            clock[0] += seconds
        with patch("time.monotonic", side_effect=lambda: clock[0]), patch("time.sleep", side_effect=sleep):
            with self.assertRaises(TextInputUnconfirmed):
                device.confirm_text(TEXT, "before_dismiss")
        self.assertAlmostEqual(clock[0], 60)
        self.assertEqual(len(device.timeouts), 4)
        self.assertLess(device.timeouts[-1], 18.3)
        self.assertTrue(all(c == QUERY for c in device.commands))
