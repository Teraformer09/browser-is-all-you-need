"""Exact character transport and verifier binding; no Android or model calls."""
import copy
import shlex
import unittest
from unittest.mock import patch

import test_text_readback as fixtures
from amazon_improved_task_001.verification.strict import expected_inputs, evaluate


class CharacterFixture(fixtures.BoundReadbackFixture):
    input_readback_contract = "persisted_text_chars_v1"

    def execute(self, action, target):
        start = len(self.trace)
        super().execute(action, target)
        if action["type"] != "type_text" or not action["text"]:
            return
        position = next(i for i in range(start, len(self.trace))
                        if self.trace[i]["args"][:3] == ["shell", "input", "text"])
        original = self.trace[position]
        chunks = []
        for char in action["text"]:
            item = copy.deepcopy(original)
            item["args"][-1] = shlex.quote(char.replace(" ", "%s"))
            chunks.append(item)
        self.trace[position:position+1] = chunks
        for record in self.input_readbacks:
            record["trace_index"] += len(chunks) - 1


class CharacterInputTests(unittest.TestCase):
    def test_exact_once_character_sequence_matches_audit(self):
        text = "Ab 1._-"
        device = fixtures.ReadbackDevice([text, text])
        action = {"type": "type_text", "element_id": "search_input", "text": text}
        with patch("time.sleep"):
            device.execute(action, fixtures.TARGET)
        native = [c for c in device.commands if c[:2] == ["shell", "input"]]
        self.assertEqual(native, expected_inputs(action, fixtures.TARGET, "persisted_text_chars_v1"))
        self.assertEqual([c[-1] for c in native if c[2] == "text"], list("Ab") + ["%s"] + list("1._-"))

    def test_dispatch_deadline_stops_without_replay(self):
        device = fixtures.ReadbackDevice([])
        clock = [0]
        original = device.command
        def slow(*args, timeout=30):
            clock[0] += 30
            return original(*args, timeout=timeout)
        with patch("time.monotonic", side_effect=lambda: clock[0]), patch.object(device, "command", side_effect=slow):
            with self.assertRaisesRegex(TimeoutError, "dispatch deadline"):
                device.execute({"type": "type_text", "element_id": "search_input", "text": fixtures.TEXT}, fixtures.TARGET)
        self.assertEqual(len(device.commands), 4)
        self.assertEqual(device.input_readbacks, [])

    def test_full_task_character_receipts_pass_and_tampering_cannot(self):
        helper = fixtures.TextReadbackAuditTests()
        helper.setUp()
        try:
            original = helper.episode
            helper.episode = lambda: original(CharacterFixture)
            episode = helper.complete()
            self.assertEqual(episode.finalize()["status"], "PASS")
            for mutation in ("wrong_character", "extra_character", "wrong_contract"):
                context = copy.deepcopy(episode.context)
                first = context["transitions"][0]
                index = next(i for i in range(first["trace_start"], first["trace_end"])
                             if context["adb_trace"][i]["args"][:3] == ["shell", "input", "text"])
                if mutation == "wrong_character": context["adb_trace"][index]["args"][-1] = "Z"
                elif mutation == "extra_character": context["adb_trace"][index]["args"][-1] += "Z"
                else: first["receipt"]["input_readback_contract"] = "persisted_text_v1"
                self.assertNotEqual(evaluate(context)["status"], "PASS", mutation)
        finally:
            helper.doCleanups()
