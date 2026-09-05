"""Approval guards and transport quoting; all checks are offline."""
import asyncio
import copy
from dataclasses import replace
from types import SimpleNamespace
import contextlib
import io
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from uber_clone_031.harness.device import TracedAdbDevice
from uber_clone_031.integrations.prime_env import UberClone031Env
from uber_clone_031.cli import main
from uber_clone_031.verification.runner import verify_episode
from test_policy_verifiers import fixture
from test_verifier import task031
from uber_clone_031.harness.evidence import EvidenceEnv
from uber_clone_031.verification.records import verify


class ApprovalAndExportTests(unittest.TestCase):
    def test_cli_cannot_start_without_explicit_confirmation(self):
        with patch("sys.argv", ["run_evidence", "--policy", "scripted", "--output-dir", "/tmp/not-started"]), \
             patch("uber_clone_031.cli.TracedAdbDevice") as device, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: main()
            self.assertEqual(error.exception.code, 2)
            device.assert_not_called()

    def test_prime_loader_does_not_authorize_device_execution(self):
        environment = UberClone031Env()
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            environment._create_env()

    def test_shell_entrypoint_stops_before_emulator(self):
        script = Path(__file__).resolve().parents[1] / "scripts/run_eval.sh"
        result = subprocess.run(["bash", str(script)], env={**os.environ, "ALLOW_UBER031_EVAL":"0"},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Evaluation disabled", result.stderr)

    def test_typed_text_is_one_quoted_shell_argument(self):
        device = TracedAdbDevice()
        for text in ("Airport Road", "alpha; beta", "quote' and \"double\"", "pipe | symbol", "value & next"):
            encoded = device._escape_input_text(text)
            self.assertEqual(shlex.split(encoded), [text.replace("%", "%25").replace(" ", "%s")])

    def test_actual_prime_rubric_keeps_negative_reward(self):
        environment = UberClone031Env()
        state = {"episode_verdict":{"status":"FAIL", "reward":-1, "training_eligible":True},
                 "android_success":False, "android_observation":{}, "prompt":[], "completion":[],
                 "answer":"", "info":{}, "task":"uber_clone_031", "trajectory":[]}
        asyncio.run(environment.rubric.score_rollout(state))
        self.assertEqual(state["reward"], -1.0)

    def test_terminal_export_contains_all_70_results_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = fixture(root)
            root.joinpath("policies").mkdir()
            task = replace(task031(), episode_id="fixture-episode")
            for frame in context["frames"]:
                frame["scorecard"] = verify(task, frame["observation"]["prefs_xml"], steps=frame["index"])
            context["frames"][0]["adb_events"][0]["phase"] = "setup"
            wrapper = EvidenceEnv.__new__(EvidenceEnv)
            wrapper.env = SimpleNamespace(task=task)
            wrapper.registry = context["registry"]
            wrapper.records = context["frames"]
            wrapper.run_dir = root
            wrapper.installed_apk = context["installed_apk"]
            wrapper.expected_apk_sha256 = context["expected_apk_sha256"]
            wrapper.verdict = None
            wrapper.last_observation = {"scorecard":wrapper.records[-1]["scorecard"]}
            verdict = wrapper.finalize()
            self.assertEqual(verdict["reward"], 1)
            self.assertEqual(len(list(root.joinpath("policies").glob("*.json"))), 14)
            self.assertTrue(root.joinpath("verifier_results.json").exists())
            self.assertIs(wrapper.finalize(), verdict)
            self.assertFalse(wrapper.last_observation["reward_pending"])

    def test_completed_booking_does_not_erase_t7_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            context = fixture(Path(directory))
            context["frames"][1]["info"].update(action_executed=False, stage_transition_accepted=False, failure_origin="agent")
            verdict = verify_episode(context)
            self.assertEqual(verdict["status"], "FAIL")
            self.assertEqual(verdict["reward"], -1)
            t6 = next(p for p in verdict["policies"] if p["policy_id"] == "T6")
            self.assertEqual(t6["status"], "PASS")


if __name__ == "__main__": unittest.main()
