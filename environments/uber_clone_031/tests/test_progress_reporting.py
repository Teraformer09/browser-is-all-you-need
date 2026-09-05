"""Checkpoint positives must remain visible without weakening terminal scoring."""
import copy
from pathlib import Path
import tempfile
import unittest

from test_policy_verifiers import fixture
from test_verifier import task031, xml_for
from dataclasses import replace
from uber_clone_031.verification.progress import checkpoint_report, markdown_timeline
from uber_clone_031.verification.runner import verify_episode
from uber_clone_031.verification.records import verify


class ProgressReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.context = fixture(Path(self.tmp.name))
        self.task = replace(task031(), episode_id="fixture-episode")

    def tearDown(self):
        self.tmp.cleanup()

    def stage_score(self, context, previous=None):
        frame = context["frames"][-1]
        return verify(self.task, frame["observation"]["prefs_xml"], steps=frame["index"], previous=previous)

    def test_pickup_policy_plus_one_is_visible_before_final_reward(self):
        context = {**self.context, "frames":self.context["frames"][:2]}
        report, snapshot = checkpoint_report(context, self.stage_score(context))
        self.assertEqual(report["completed_stages"], 1)
        self.assertEqual(report["policies"]["T1"]["reward"], 1)
        self.assertEqual(report["newly_completed_stages"], ["pickup"])
        self.assertIsNone(report["episode_reward"])
        self.assertEqual(report["episode_status"], "PENDING")
        self.assertEqual(report["policies"]["T6"]["status"], "PENDING")
        self.assertEqual(sum(len(p["verifier_results"]) for p in snapshot["policies"]), 70)
        self.assertIn("T1=+1", markdown_timeline([report]))

    def test_repeated_check_does_not_accumulate_reward(self):
        context = {**self.context, "frames":self.context["frames"][:2]}
        stage = self.stage_score(context)
        first, _ = checkpoint_report(context, stage)
        second, _ = checkpoint_report(context, stage, first)
        self.assertEqual(second["newly_completed_stages"], [])
        self.assertEqual(second["policies"]["T1"]["reward"], 1)
        self.assertIsNone(second["episode_reward"])

    def test_wrong_later_pickup_revokes_provisional_pass(self):
        context = {**self.context, "frames":copy.deepcopy(self.context["frames"][:2])}
        stage = self.stage_score(context)
        first, _ = checkpoint_report(context, stage)
        frame = context["frames"][-1]
        state = {**frame["runtime_probe"], "ride_pickup":"Wrong pickup"}
        frame["runtime_probe"] = state
        frame["observation"]["prefs_xml"] = xml_for(state)
        frame["mutations"][-1]["state"] = state
        # Remove the old UI/OCR channel instead of reusing its outdated positive.
        frame["observation"]["ui_tree_xml"] = ""
        frame["ocr"] = {"error":"NO_CURRENT_IMAGE"}
        changed, _ = checkpoint_report(context, self.stage_score(context, stage), first)
        self.assertEqual(changed["invalidated_stages"], ["pickup"])
        self.assertEqual(changed["policies"]["T1"]["reward"], -1)

    def test_terminal_failure_does_not_erase_other_policy_positives(self):
        context = copy.deepcopy(self.context)
        context["frames"][1]["info"].update(action_executed=False, stage_transition_accepted=False, failure_origin="agent")
        verdict = verify_episode(context)
        report, _ = checkpoint_report(context, self.stage_score(context), final_verdict=verdict)
        self.assertEqual(report["episode_reward"], -1)
        self.assertEqual(report["policies"]["T1"]["reward"], 1)
        self.assertEqual(report["policies"]["T7"]["reward"], -1)

    def test_genuine_complete_fixture_has_all_policies_plus_one(self):
        verdict = verify_episode(self.context)
        report, _ = checkpoint_report(self.context, self.stage_score(self.context), final_verdict=verdict)
        self.assertEqual(report["episode_reward"], 1)
        self.assertEqual(report["completed_stages"], 6)
        self.assertTrue(all(p["reward"] == 1 for p in report["policies"].values()))


if __name__ == "__main__": unittest.main()
