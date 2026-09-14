"""Input delivery regression tests; fakes only, no model or Android calls."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch

from amazon_improved_task_001.harness.evidence import digest
from amazon_improved_task_001.harness.peach import PACKAGE, PeachDevice, TextInputUnconfirmed
from amazon_improved_task_001.harness.peach_episode import PeachEpisode
from amazon_improved_task_001.verification.strict import evaluate
from test_strict_verification import FixtureDevice

QUERY = ["shell", "content", "query", "--uri", "content://" + PACKAGE + ".verifier/state"]
TEXT = "Trail Steel Water Bottle"
TARGET = {"bounds": [10, 10, 100, 60]}
FOCUSED_XML = ('<hierarchy><node package="' + PACKAGE + '" resource-id="' + PACKAGE + ':id/etSearchBox" '
               'text="" content-desc="" enabled="true" clickable="true" focused="true" '
               'class="android.widget.EditText" bounds="[10,10][900,60]"/></hierarchy>').encode()


class ReadbackDevice(PeachDevice):
    def __init__(self, drafts):
        super().__init__("FAKE")
        self.drafts = iter(drafts)
        self.commands = []
        self.phase = "action"

    def ui(self):
        remote = "/sdcard/peach-ui-" + "d" * 32 + ".xml"
        for args, raw in ((["shell", "uiautomator", "dump", remote], b""),
                          (["exec-out", "cat", remote], FOCUSED_XML),
                          (["shell", "rm", "-f", remote], b"")):
            self.trace.append({"args": args, "returncode": 0, "bytes": len(raw),
                               "sha256": digest(raw), "phase": self.phase})
        return FOCUSED_XML

    def command(self, *args, timeout=30):
        self.commands.append(list(args))
        raw = b""
        if list(args) == QUERY:
            draft = next(self.drafts)
            if isinstance(draft, Exception): raise draft
            raw = ("Row: 0 snapshot=" + json.dumps({"eval_session": [
                {"episode_id": "peach_" + "a" * 32, "draft": draft}]})).encode()
        self.trace.append({"args": list(args), "returncode": 0, "bytes": len(raw),
                           "sha256": digest(raw), "phase": self.phase})
        return raw


class TextReadbackTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch("time.sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def action(self, device, text=TEXT):
        device.execute({"type": "type_text", "element_id": "search_input", "text": text}, TARGET)

    def test_complete_text_confirmed_before_and_after_dismiss(self):
        device = ReadbackDevice([TEXT, TEXT])
        self.action(device)
        self.assertEqual([r["stage"] for r in device.input_readbacks], ["before_dismiss", "after_dismiss"])
        back = device.commands.index(["shell", "input", "keyevent", "KEYCODE_BACK"])
        self.assertEqual(device.commands[back - 1], QUERY)
        self.assertEqual(device.commands[back + 1], QUERY)
        self.assertTrue(all(r["confirmed"] for r in device.input_readbacks))

    def test_lagging_last_word_is_waited_for_not_retyped(self):
        device = ReadbackDevice(["Trail Steel Water ", TEXT, TEXT])
        self.action(device)
        self.assertEqual([r["confirmed"] for r in device.input_readbacks], [False, True, True])
        self.assertEqual(sum(c[:3] == ["shell", "input", "text"] for c in device.commands), len(TEXT))

    def test_permanent_truncation_never_dismisses_or_replays(self):
        device = ReadbackDevice(["Trail Steel Water "] * 5)
        with self.assertRaisesRegex(TextInputUnconfirmed, "before_dismiss"):
            self.action(device)
        self.assertEqual(len(device.input_readbacks), 5)
        self.assertNotIn(["shell", "input", "keyevent", "KEYCODE_BACK"], device.commands)
        self.assertEqual(sum(c[:3] == ["shell", "input", "text"] for c in device.commands), len(TEXT))

    def test_text_change_during_dismiss_is_detected(self):
        device = ReadbackDevice([TEXT] + ["Trail Steel Water "] * 5)
        with self.assertRaisesRegex(TextInputUnconfirmed, "after_dismiss"):
            self.action(device)
        self.assertEqual(sum(c == ["shell", "input", "keyevent", "KEYCODE_BACK"] for c in device.commands), 1)

    def test_empty_text_is_verified_as_empty_not_a_ui_hint(self):
        device = ReadbackDevice(["", ""])
        self.action(device, "")
        self.assertFalse(any(c[:3] == ["shell", "input", "text"] for c in device.commands))
        self.assertTrue(all(r["actual"] == "" for r in device.input_readbacks))

    def test_failed_probe_is_not_retried_as_an_input(self):
        device = ReadbackDevice([RuntimeError("provider unavailable")])
        with self.assertRaisesRegex(TextInputUnconfirmed, "state read failed"):
            self.action(device)
        self.assertEqual(device.commands.count(QUERY), 1)

    def test_other_actions_do_not_get_input_probes(self):
        device = ReadbackDevice([])
        device.execute({"type": "tap_element", "element_id": "cart_button"}, TARGET)
        self.assertEqual(device.commands, [["shell", "input", "tap", "55", "35"]])
        self.assertEqual(device.input_readbacks, [])


class BoundReadbackFixture(FixtureDevice):
    input_readback_contract = "persisted_text_v1"

    def execute(self, action, target):
        self.input_readbacks = []
        super().execute(action, target)
        if action["type"] != "type_text": return
        back = self.trace.pop()
        self.assert_back(back)
        raw = ("Row: 0 snapshot=" + json.dumps(self.tables)).encode()
        for stage in ("before_dismiss", "after_dismiss"):
            if stage == "after_dismiss": self.trace.append(back)
            index = len(self.trace)
            self.trace_entry(QUERY, raw)
            self.input_readbacks.append({"stage": stage, "trace_index": index,
                "expected": action["text"], "actual": action["text"], "episode_id": self.episode,
                "confirmed": True, "raw": raw})

    @staticmethod
    def assert_back(entry):
        if entry["args"] != ["shell", "input", "keyevent", "KEYCODE_BACK"]:
            raise AssertionError("Fixture input contract changed")


class TextReadbackAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def episode(self, device=BoundReadbackFixture):
        with patch("amazon_improved_task_001.harness.peach_episode.PeachDevice", device):
            episode = PeachEpisode("FAKE", "FAKE.apk", self.temp.name, rubric_profile="peach_strict_v1")
        episode.reset()
        return episode

    def complete(self):
        episode = self.episode()
        for item in episode.task["expected_items"]:
            for action in ({"type": "type_text", "element_id": "search_input", "text": item["query"]},
                           {"type": "tap_element", "element_id": "search_button"},
                           {"type": "tap_element", "element_id": "add_" + item["sku"]}):
                episode.step(json.dumps(action))
        episode.step('{"type":"tap_element","element_id":"cart_button"}')
        episode.step('{"type":"finish"}')
        return episode

    def test_complete_task_with_bound_readbacks_still_passes(self):
        episode = self.complete()
        result = episode.finalize()
        self.assertEqual(result["status"], "PASS", result["reason_codes"])
        first = episode.transitions[0]
        self.assertEqual(first["receipt"]["input_readback_contract"], "persisted_text_v1")
        self.assertEqual(len(first["input_readbacks"]), 2)

    def test_missing_tampered_or_reordered_probes_cannot_pass(self):
        episode = self.complete()
        for kind in ("missing", "wrong_value", "wrong_position", "unexpected_command", "undeclared"):
            with self.subTest(kind=kind):
                context = copy.deepcopy(episode.context)
                transition = context["transitions"][0]
                record = transition["input_readbacks"][0]
                if kind == "missing": transition["input_readbacks"] = []
                if kind == "wrong_value": record["actual"] = "wrong"
                if kind == "wrong_position": record["trace_index"] += 1
                if kind == "unexpected_command":
                    context["adb_trace"][record["trace_index"]]["args"] = ["shell", "input", "tap", "1", "1"]
                if kind == "undeclared": transition["receipt"].pop("input_readback_contract")
                self.assertNotEqual(evaluate(context)["status"], "PASS")

    def test_probe_file_tampering_is_rejected(self):
        episode = self.complete()
        record = episode.transitions[0]["input_readbacks"][0]
        (episode.root / record["artifact"]["path"]).write_text("not a provider response")
        self.assertNotEqual(evaluate(episode.context)["status"], "PASS")

    def test_malformed_action_does_not_reuse_previous_readbacks(self):
        episode = self.episode()
        episode.step('{"type":"type_text","element_id":"search_input","text":"headphones"}')
        episode.step('[]')
        self.assertEqual(episode.transitions[-1]["input_readbacks"], [])
        self.assertFalse(episode.transitions[-1]["receipt"]["schema_valid"])

    def test_unconfirmed_delivery_is_pipeline_invalid_not_agent_failure(self):
        class LostInput(BoundReadbackFixture):
            def execute(self, action, target):
                super().execute(action, target)
                self.tables["eval_session"][0]["draft"] = "Trail Steel Water "
                self.viewport()
                raise TextInputUnconfirmed("after_dismiss: observed truncation")
        episode = self.episode(LostInput)
        episode.step(json.dumps({"type":"type_text", "element_id":"search_input", "text":TEXT}))
        receipt = episode.transitions[-1]["receipt"]
        self.assertEqual(receipt["failure_origin"], "pipeline")
        self.assertTrue(receipt["executed"])
        self.assertFalse(receipt["accepted"])
        self.assertTrue(episode.done)
        result = episode.finalize()
        self.assertEqual((result["status"], result["reward"], result["training_eligible"]), ("INVALID", 0, False))


if __name__ == "__main__": unittest.main()
