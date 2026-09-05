"""Fast harness tests; app-side mutation rules are additionally tested on Android."""
import subprocess
import unittest
from unittest.mock import patch

from uber_clone_031.harness.backend.adb_device import AdbDevice
from uber_clone_031.harness.episode import RideStageEnv
from uber_clone_031.harness.device import TracedAdbDevice
from test_verifier import task031, xml_for


class StateDevice(AdbDevice):
    def __init__(self):
        super().__init__()
        self.state = {"episode_id": "new-episode", "journey_stage": "0", "ride_pickup": "",
                      "ride_drop": "", "ride_type": "", "selected_ride": "", "payment": "",
                      "ride_action_sequence": "0", "last_action_accepted": "true",
                      "sequence_error": "false", "ride_confirmed": "false", "ride_cancelled": "false", "screen": "ride"}
        self.executed = []

    def dump_ui(self):
        names = task031().resource_names
        return '<hierarchy>' + "".join(
            f'<node resource-id="{self.package}:id/{name}" text="" bounds="[0,0][100,100]" enabled="true" clickable="true" />'
            for name in names) + '</hierarchy>'

    def read_shared_prefs(self): return xml_for(self.state)

    def click_resource(self, target):
        self.executed.append(target)
        self.state["ride_action_sequence"] = str(int(self.state["ride_action_sequence"]) + 1)
        self.state["last_action_accepted"] = "true"
        if target == "ride_type_premium":
            self.state.update(ride_type="Premium", journey_stage="1")
        elif target == "destination_search_button":
            if not self.state["ride_drop"]:
                self.state.update(last_action_accepted="false", last_action_error="Enter a destination before searching.")
            else:
                self.state["journey_stage"] = "2"

    def input_resource(self, target, value):
        self.executed.append(target)
        self.state[{"pickup_input": "ride_pickup", "drop_input": "ride_drop"}[target]] = value
        self.state["ride_action_sequence"] = str(int(self.state["ride_action_sequence"]) + 1)
        self.state["last_action_accepted"] = "true"


class StageContractTests(unittest.TestCase):
    def setUp(self):
        self.device = StateDevice()
        self.env = RideStageEnv(task=task031(), device=self.device)

    def test_premature_payment_no_execution_no_mutation(self):
        before = dict(self.device.state)
        result = self.env.step({"type": "tap_element", "element_id": "payment_card"})
        self.assertFalse(result.done)
        self.assertFalse(result.info["action_executed"])
        self.assertFalse(result.info["stage_transition_accepted"])
        self.assertIn("Choose a cab", result.info["rejection_reason"])
        self.assertEqual(self.device.state, before)
        self.assertEqual(self.device.executed, [])

    def test_invalid_finish_continues_and_later_action_works(self):
        result = self.env.step({"type": "finish"})
        self.assertFalse(result.done)
        self.assertFalse(result.info["action_executed"])
        result = self.env.step({"type": "type_text", "element_id": "pickup_input", "text": "Airport Road"})
        self.assertTrue(result.info["stage_transition_accepted"])
        self.assertEqual(result.observation["scorecard"]["completed_stages"], 1)
        self.assertAlmostEqual(result.reward, 1/6)

    def test_malformed_json_never_crashes_and_uses_budget(self):
        for raw in (None, 9, [], "[]", "null", "5", '"text"', {"type": []}, {"type": {}},
                    {"type": "type_text", "element_id": "pickup_input", "text": 9}, "invalid"):
            with self.subTest(raw=raw):
                env = RideStageEnv(task=task031(), device=StateDevice())
                result = env.step(raw)
                self.assertFalse(result.info["schema_valid"])
                self.assertFalse(result.info["action_executed"])
                self.assertEqual(env.steps, 1)
                self.assertFalse(result.done)

    def test_invalid_actions_cannot_exceed_budget(self):
        for _ in range(12):
            result = self.env.step("[]")
        self.assertTrue(result.done)
        self.assertEqual(result.info["termination_reason"], "step_budget")
        self.env.step("[]")
        self.assertEqual(self.env.steps, 12)

    def test_execution_and_app_acceptance_are_distinct(self):
        self.env.step({"type": "tap_element", "element_id": "ride_type_premium"})
        result = self.env.step({"type": "tap_element", "element_id": "destination_search_button"})
        self.assertTrue(result.info["action_executed"])
        self.assertFalse(result.info["stage_transition_accepted"])
        self.assertIn("Enter a destination", result.observation["last_error"])
        self.assertFalse(result.done)
        self.env.step({"type": "type_text", "element_id": "drop_input", "text": "City Centre"})
        result = self.env.step({"type": "tap_element", "element_id": "destination_search_button"})
        self.assertTrue(result.info["stage_transition_accepted"])
        self.assertTrue(result.observation["scorecard"]["stages"]["destination"]["completed"])

    def test_final_success_survives_a_recovered_invalid_action(self):
        self.env.step({"type": "finish"})
        self.device.state.update(self.env.task.expected_state())
        result = self.env.step({"type": "finish"})
        self.assertTrue(result.done)
        self.assertTrue(result.observation["scorecard"]["safe_success"])

    def test_ui_failure_does_not_reuse_cached_observation(self):
        self.env.observe()
        with patch.object(self.device, "dump_ui", side_effect=RuntimeError("fresh dump failed")):
            obs = self.env.observe()
        self.assertEqual(obs["ui"], [])
        self.assertEqual(obs["ui_tree_xml"], "")
        self.assertIn("fresh dump failed", obs["ui_error"])
        self.assertFalse(obs["scorecard"]["evaluation_valid"])

    def test_find_resource_never_scrolls_implicitly(self):
        device = TracedAdbDevice()
        with patch.object(device, "dump_ui", return_value="<hierarchy/>"), patch.object(device, "swipe") as swipe:
            with self.assertRaises(LookupError):
                device.find_resource("payment_card")
            swipe.assert_not_called()

    def test_failed_dump_is_not_read_as_fresh(self):
        device = TracedAdbDevice()
        failure = subprocess.CalledProcessError(1, ["adb"])
        def adb(*args, **kwargs):
            if "uiautomator" in args: raise failure
            return subprocess.CompletedProcess(args, 0, "", "")
        with patch.object(device, "adb", side_effect=adb) as calls:
            with self.assertRaises(subprocess.CalledProcessError):
                device.dump_ui()
            self.assertFalse(any("cat" in call.args for call in calls.call_args_list))
        self.assertFalse(device.observation_freshness["fresh"])
        self.assertFalse(device.observation_freshness["fallback_used"])

    def test_transport_records_internal_commands_and_failure(self):
        device = TracedAdbDevice()
        with patch.object(AdbDevice, "adb", return_value=subprocess.CompletedProcess([], 0, "ok", "")):
            device.adb("shell", "input", "keyevent", "KEYCODE_BACK")
        self.assertEqual(device.trace[-1]["returncode"], 0)
        with patch.object(AdbDevice, "adb", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError): device.adb("shell", "getprop")
        self.assertIn("offline", device.trace[-1]["error"])


if __name__ == "__main__": unittest.main()
