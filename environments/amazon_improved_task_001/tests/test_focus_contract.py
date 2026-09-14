"""persisted_text_chars_v2: focus-probe audit — accepted when honest, rejected when forged."""
import copy
import json
import unittest

import test_text_readback as fixtures
from amazon_improved_task_001.verification.strict import evaluate


import test_character_input


class FocusFixture(test_character_input.CharacterFixture):
    """v2 device: per-char input plus a hash-bound focus probe triple after the tap."""
    input_readback_contract = "persisted_text_chars_v2"

    def execute(self, action, target):
        if action["type"] == "type_text":
            self.focus_probes = []
        start = len(self.trace)
        super().execute(action, target)
        if action["type"] != "type_text":
            return
        tap = next(i for i in range(start, len(self.trace))
                   if self.trace[i]["args"][:3] == ["shell", "input", "tap"])
        remote = "/sdcard/peach-ui-" + "d" * 32 + ".xml"
        triple = [
            {"args": ["shell", "uiautomator", "dump", remote], "returncode": 0, "bytes": 0,
             "sha256": fixtures.digest(b""), "phase": self.phase},
            {"args": ["exec-out", "cat", remote], "returncode": 0, "bytes": len(fixtures.FOCUSED_XML),
             "sha256": fixtures.digest(fixtures.FOCUSED_XML), "phase": self.phase},
            {"args": ["shell", "rm", "-f", remote], "returncode": 0, "bytes": 0,
             "sha256": fixtures.digest(b""), "phase": self.phase},
        ]
        self.trace[tap + 1:tap + 1] = triple
        for record in self.input_readbacks:
            record["trace_index"] += 3
        self.focus_probes = [{"trace_index": tap + 2, "focused": True, "raw": fixtures.FOCUSED_XML}]


class FocusContractTests(unittest.TestCase):
    def build(self, device=FocusFixture):
        helper = fixtures.TextReadbackAuditTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        original = helper.episode
        helper.episode = lambda: original(device)
        return helper.complete()

    def test_focus_confirmed_episode_passes(self):
        episode = self.build()
        self.assertEqual(episode.finalize()["status"], "PASS")
        probes = episode.context["transitions"][0]["focus_probes"]
        self.assertEqual(len(probes), 1)
        self.assertTrue(probes[0]["focused"])
        self.assertEqual(evaluate(episode.context)["status"], "PASS")

    def test_forged_focus_claim_is_rejected(self):
        episode = self.build()
        context = copy.deepcopy(episode.context)
        context["transitions"][0]["focus_probes"][0]["focused"] = False
        self.assertNotEqual(evaluate(context)["status"], "PASS")

    def test_probe_hash_tampering_is_rejected(self):
        episode = self.build()
        context = copy.deepcopy(episode.context)
        context["transitions"][0]["focus_probes"][0]["artifact"]["sha256"] = "0" * 64
        self.assertNotEqual(evaluate(context)["status"], "PASS")

    def test_v1_marker_with_probes_is_rejected(self):
        episode = self.build()
        context = copy.deepcopy(episode.context)
        context["transitions"][0]["receipt"]["input_readback_contract"] = "persisted_text_chars_v1"
        self.assertNotEqual(evaluate(context)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
