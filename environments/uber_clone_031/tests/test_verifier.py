import unittest
import xml.etree.ElementTree as ET
from dataclasses import replace

from uber_clone_031.harness.backend.tasks.ride_booking import RideBookingTask
from uber_clone_031.verification.records import verify
from uber_clone_031.harness.evidence import validate_png


def xml_for(state):
    root = ET.Element("map")
    for key, value in state.items():
        ET.SubElement(root, "string", name=key).text = str(value)
    return ET.tostring(root, encoding="unicode")


def task031():
    return RideBookingTask(task_id="uber_clone_031", episode_id="new-episode", pickup="Airport Road",
                           destination="City Centre", ride_type="Premium", selected_ride="Premium",
                           payment="card", max_steps=12)


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.task = task031()
        self.state = {**self.task.expected_state(), "ride_cancelled": "false"}

    def score(self, state=None, **kwargs):
        opts = dict(steps=7, invalid=False, forbidden=False, execution_errors=[], evidence_ok=True)
        opts.update(kwargs)
        return verify(self.task, xml_for(self.state if state is None else state), **opts)

    def test_correct_booking(self):
        score = self.score()
        self.assertEqual(score["reward"], 1.0)
        self.assertEqual(score["completed_stages"], 6)
        self.assertTrue(score["task_success"])

    def test_every_required_field_wrong_or_missing_prevents_final_success(self):
        for key in self.state:
            for mode in ("wrong", "missing"):
                with self.subTest(key=key, mode=mode):
                    state = dict(self.state)
                    if mode == "wrong": state[key] = "incorrect"
                    else: del state[key]
                    score = self.score(state)
                    self.assertEqual(score["final_reward"], 0.0)
                    self.assertFalse(score["task_success"])
                    self.assertLess(score["reward"], 1.0)

    def test_independent_partial_stages_do_not_erase_completed_work(self):
        score = self.score({**self.state, "ride_pickup": "wrong"})
        self.assertEqual(score["completed_stages"], 4)
        self.assertTrue(score["stages"]["payment"]["completed"])
        self.assertFalse(score["stages"]["booking"]["completed"])

    def test_exact_progress_for_each_stage(self):
        state = {key: "" for key in self.state}
        state.update(episode_id=self.task.episode_id, journey_stage="0", sequence_error="false", ride_cancelled="false")
        self.assertEqual(self.score(state)["reward"], 0.0)
        for count, (field, stage) in enumerate((("ride_pickup", 0), ("ride_type", 1), ("ride_drop", 2),
                                                ("selected_ride", 3), ("payment", 4)), 1):
            state[field] = self.state[field]
            state["journey_stage"] = str(stage)
            score = self.score(state)
            self.assertEqual(score["completed_stages"], count)
            self.assertAlmostEqual(score["reward"], count / 6)
            self.assertFalse(score["task_success"])

    def test_typing_destination_alone_does_not_count_as_search(self):
        score = self.score({**self.state, "journey_stage": "1"})
        self.assertFalse(score["stages"]["destination"]["completed"])
        self.assertEqual(score["stages"]["destination"]["status"], "in_progress")

    def test_invalidated_stage_retains_history(self):
        old = self.score()
        score = self.score({**self.state, "payment": "", "journey_stage": "3", "ride_confirmed": "false"},
                           previous=old)
        self.assertEqual(score["stages"]["payment"]["status"], "invalidated")
        self.assertTrue(score["stages"]["payment"]["ever_completed"])
        self.assertEqual(score["stages"]["payment"]["first_completed_step"], 7)

    def test_rejection_is_reported_without_poisoning_recovery(self):
        score = self.score({**self.state, "journey_stage": "1", "payment": ""},
                           action={"type": "tap_element", "element_id": "payment_card"},
                           action_info={"stage_transition_accepted": False, "rejection_reason": "Choose a cab"})
        self.assertEqual(score["stages"]["payment"]["status"], "rejected")
        self.assertEqual(score["stages"]["payment"]["rejection_reason"], "Choose a cab")
        self.assertTrue(self.score(invalid=True)["safe_success"])
        self.assertFalse(self.score(invalid=True)["process"]["no_invalid_action"])

    def test_forbidden_and_over_budget_are_separate_from_outcome(self):
        for opts in ({"forbidden": True}, {"steps": 13}):
            score = self.score(**opts)
            self.assertTrue(score["outcome_success"])
            self.assertFalse(score["safe_success"])

    def test_infra_and_missing_images_invalidate_eval_not_partial_work(self):
        for opts in ({"execution_errors": ["emulator offline"]}, {"evidence_ok": False}):
            score = self.score(**opts)
            self.assertFalse(score["safe_success"])
            self.assertFalse(score["evaluation_valid"])
            self.assertEqual(score["completed_stages"], 6)

    def test_empty_malformed_duplicate_and_stale_state_fail(self):
        for xml in ("", "<map>", "<other/>", '<map><string name="screen">x</string><string name="screen">ride_booked</string></map>',
                    xml_for({**self.state, "episode_id": "old"})):
            score = verify(self.task, xml, steps=7)
            self.assertEqual(score["completed_stages"], 0)
            self.assertFalse(score["outcome_success"])

    def test_no_legacy_weight_dependency(self):
        expected = self.score()
        self.task = replace(self.task, reward_weights={"destination_match": 9999})
        self.assertEqual(expected, self.score())

    def test_empty_or_text_screenshots_rejected(self):
        for data in (b"", b"fake png", b"\x89PNG\r\n\x1a\n"):
            with self.assertRaises(ValueError): validate_png(data)


if __name__ == "__main__": unittest.main()
