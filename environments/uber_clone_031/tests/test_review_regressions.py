"""Qodo regressions: synthetic evidence and fake devices; no eval/API calls."""
import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_policy_verifiers import fixture
from test_stage_contract import StateDevice
from test_verifier import task031
from uber_clone_031.harness.backend.apk_env import DummyApkEnv
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.harness.ocr import capture_ocr
from uber_clone_031.verification.checks import VERIFIERS
from uber_clone_031.verification.evidence_readers import Unassessable, summary_state

ROUTE = "Pickup: Airport Road | Ride: Premium | Destination: City Centre | Cab: Premium | Payment: card"
PROGRESS = "Booking step 5/5 \u2022 Pickup: set"
TERMINAL = "Ride booked: Premium to City Centre"


def visual_results(context, channel):
    return [function(context) for identifier, function in VERIFIERS.values()
            if identifier.split(".")[0] in {"T1", "T2", "T3", "T4", "T5", "T6"}
            and identifier.endswith(".V" + str(channel))]


class SummaryRegressionTests(unittest.TestCase):
    def test_real_progress_is_not_a_duplicate_route(self):
        for progress in (PROGRESS, PROGRESS.replace("\u2022", "\u00b7"), PROGRESS.replace("\u2022 ", "")):
            for text in (progress + " " + ROUTE + " " + TERMINAL,
                         ROUTE + " " + progress + " " + TERMINAL):
                with self.subTest(text=text):
                    state = summary_state(text)
                    self.assertEqual(state["ride_pickup"], "Airport Road")
                    self.assertEqual(state["payment"], "card")
                    self.assertEqual(state["journey_stage"], "5")
                    self.assertEqual(state["ride_confirmed"], "true")

    def test_unset_progress_does_not_invent_a_pickup(self):
        text = "Booking step 0/5 \u2022 Pickup: not set " + ROUTE.replace("Airport Road", "not set")
        state = summary_state(text)
        self.assertEqual(state["ride_pickup"], "")
        self.assertEqual(state["journey_stage"], "0")

    def test_genuine_duplicate_routes_remain_ambiguous(self):
        for other in (ROUTE, ROUTE.replace("card", "cash")):
            with self.subTest(other=other):
                with self.assertRaisesRegex(Unassessable, "SUMMARY_DUPLICATED_OR_AMBIGUOUS"):
                    summary_state(PROGRESS + " " + ROUTE + " " + other + " " + TERMINAL)

    def test_unattributed_pickup_label_is_not_silently_ignored(self):
        with self.assertRaisesRegex(Unassessable, "SUMMARY_DUPLICATED_OR_AMBIGUOUS"):
            summary_state(ROUTE + " Pickup: set " + TERMINAL)

    def test_missing_route_still_is_unassessable(self):
        with self.assertRaises(Unassessable):
            summary_state(PROGRESS + " " + TERMINAL)

    def test_ocr_keeps_all_regions_without_confusing_the_parser(self):
        root = ET.Element("hierarchy")
        rows = ["left\ttop\twidth\theight\tconf\ttext"]
        for index, (name, text) in enumerate((("ride_progress_text", PROGRESS),
                                             ("route_summary_text", ROUTE),
                                             ("final_status_text", TERMINAL))):
            y = index * 200
            ET.SubElement(root, "node", {"resource-id": "test:id/" + name,
                                         "bounds": f"[0,{y}][2000,{y + 100}]"})
            for word_index, word in enumerate(text.split()):
                rows.append(f"{word_index * 40}\t{y + 10}\t30\t20\t99\t{word}")
        receipt = SimpleNamespace(stdout="\n".join(rows), stderr="")
        with patch("uber_clone_031.harness.ocr.subprocess.run", return_value=receipt):
            ocr = capture_ocr(Path("unused-offline-fixture.png"), "a" * 64,
                              ET.tostring(root, encoding="unicode"))
        self.assertEqual(len(ocr["regions"]), 3)
        self.assertEqual(ocr["text"].count("Pickup:"), 2)
        self.assertEqual(summary_state(ocr["text"])["journey_stage"], "5")


class VisualVerifierRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="uber-review-test-")
        self.addCleanup(self.tmp.cleanup)
        self.context = fixture(Path(self.tmp.name))

    def test_all_twelve_visual_slots_accept_actual_progress_text(self):
        self.assertIn(PROGRESS, self.context["frames"][-1]["ocr"]["text"])
        for channel in (2, 3):
            results = visual_results(self.context, channel)
            self.assertEqual(len(results), 6)
            for result in results:
                self.assertEqual(result["status"], "PASS", result)

    def test_duplicate_accessibility_route_nodes_are_invalid(self):
        context = copy.deepcopy(self.context)
        frame = context["frames"][-1]
        root = ET.fromstring(frame["observation"]["ui_tree_xml"])
        route = next(node for node in root.iter("node")
                     if node.get("resource-id", "").endswith("/route_summary_text"))
        root.append(copy.deepcopy(route))
        frame["observation"]["ui_tree_xml"] = ET.tostring(root, encoding="unicode")
        for result in visual_results(context, 2):
            self.assertEqual(result["status"], "INVALID", result)
            self.assertEqual(result["reason_code"], "SUMMARY_DUPLICATED_OR_AMBIGUOUS")

    def test_duplicate_screenshot_route_text_is_invalid(self):
        context = copy.deepcopy(self.context)
        context["frames"][-1]["ocr"]["text"] += " " + ROUTE
        for result in visual_results(context, 3):
            self.assertEqual(result["status"], "INVALID", result)
            self.assertEqual(result["reason_code"], "SUMMARY_DUPLICATED_OR_AMBIGUOUS")


class BaseActionRegressionTests(unittest.TestCase):
    def test_malformed_values_keep_penalty_receipt_and_step_accounting(self):
        for raw in (None, [], 7, True, {"type": []}, {"type": {}}, "[]", "null",
                    {"action": []}, {"type": "tap_element", "element_id": 3}):
            with self.subTest(raw=raw):
                device = StateDevice()
                env = DummyApkEnv(task=task031(), device=device, invalid_action_penalty=-0.125)
                result = env.step(raw)
                self.assertEqual(result.reward, -0.125)
                self.assertEqual(result.info["error"], "invalid_action_schema")
                self.assertFalse(result.info["action_valid"])
                self.assertTrue(result.info["invalid_action"])
                self.assertTrue(env.invalid_action_seen)
                self.assertEqual(env.steps, 1)
                self.assertFalse(result.done)
                self.assertEqual(device.executed, [])
                self.assertEqual(env.last_action, raw if isinstance(raw, dict) else {"raw": str(raw)})

    def test_direct_schema_entry_point_rejects_nonobjects_and_nonstrings(self):
        for raw in (None, [], 7, {"type": []}, {"type": {}}, {"type": None}):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ActionValidationError, "invalid_action_schema"):
                    MobileAction.from_dict(raw)

    def test_legacy_and_modern_actions_still_match(self):
        modern = {"type": "type_text", "element_id": "pickup_input", "text": "Airport Road"}
        legacy = {"action": "input_resource", "target": "pickup_input", "text": "Airport Road"}
        env = DummyApkEnv(task=task031(), device=StateDevice())
        expected = env._coerce_action(modern).to_dict()
        for raw in (legacy, json.dumps(modern), json.dumps(legacy)):
            self.assertEqual(env._coerce_action(raw).to_dict(), expected)

    def test_malformed_input_does_not_prevent_the_next_action(self):
        device = StateDevice()
        env = DummyApkEnv(task=task031(), device=device)
        env.step([])
        result = env.step({"type": "type_text", "element_id": "pickup_input", "text": "Airport Road"})
        self.assertTrue(result.info["action_valid"])
        self.assertEqual(env.steps, 2)
        self.assertEqual(device.executed, ["pickup_input"])


class OpenAIPolicyImportTests(unittest.TestCase):
    def module(self):
        return importlib.import_module("uber_clone_031.harness.backend.policies.openai_policy")

    def test_import_does_not_need_an_api_key_or_make_a_request(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.urlopen") as request:
            module = importlib.reload(self.module())
            self.assertTrue(callable(module.OpenAIActionPolicy))
            request.assert_not_called()

    def test_explicit_key_takes_precedence(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-env-key"}):
            policy = self.module().OpenAIActionPolicy(api_key="offline-explicit-key")
            self.assertEqual(policy.api_key, "offline-explicit-key")

    def test_environment_key_is_supported(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-env-key"}):
            self.assertEqual(self.module().OpenAIActionPolicy().api_key, "offline-env-key")

    def test_missing_key_errors_at_construction_not_import(self):
        with patch.dict(os.environ, {}, clear=True):
            module = self.module()
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY is required"):
                module.OpenAIActionPolicy()


if __name__ == "__main__":
    unittest.main()
