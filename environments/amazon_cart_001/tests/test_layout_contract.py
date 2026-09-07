"""Shared layout, approval and signed-adapter checks. Never calls a model or device."""
import contextlib
import importlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from amazon_cart_001.specs import task_path
from amazon_cart_001.verification.registry import load_registry
from amazon_cart_001 import load_environment
from amazon_cart_001.integrations.prime_env import episode_reward

class LayoutTests(unittest.TestCase):
    def test_common_role_files(self):
        root = task_path().parents[1]
        for role in ("cli.py", "harness/actions.py", "harness/device.py", "harness/episode.py",
                     "harness/evidence.py", "harness/prompts.py", "harness/acceptance.py",
                     "agents/openrouter.py", "agents/scripted.py", "verification/contracts.py",
                     "verification/registry.py", "verification/evidence_readers.py",
                     "verification/scoring.py", "verification/task_checks.py", "verification/progress.py",
                     "verification/generic/validity.py", "verification/generic/interaction.py",
                     "verification/semantic.py", "integrations/prime_env.py", "integrations/prime_upload.py",
                     "specs/task.json", "specs/policies.json", "specs/scoring.json", "specs/app_contract.json"):
            with self.subTest(role=role):
                self.assertTrue((root / role).is_file())

    def test_loading_is_not_authorization(self):
        env = load_environment()
        self.assertFalse(env.allow_eval)
        self.assertEqual(len(env.eval_dataset), 1)
        self.assertEqual(env.task["task_id"], "amazon_cart_001")

    def test_cli_guard_precedes_model_or_device(self):
        cli = importlib.import_module("amazon_cart_001.cli")
        argv = ["run", "--serial", "not-a-device", "--apk", "not-an-apk", "--output-dir", "not-a-run"]
        with patch("sys.argv", argv), patch.object(cli, "model_info") as model, patch.object(cli, "Episode") as episode, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main()
            model.assert_not_called()
            episode.assert_not_called()

    def test_signed_adapter_and_invalid_default(self):
        for status, reward in (("PASS", 1), ("INVALID", 0), ("FAIL", -1)):
            self.assertEqual(episode_reward({"episode_verdict":{"status":status,"reward":reward}}), reward)
        state = {}
        self.assertEqual(episode_reward(state), 0)
        self.assertFalse(state["episode_verdict"]["training_eligible"])

    def test_one_canonical_definition(self):
        self.assertEqual(list((task_path().parents[2] / "task").glob("*.json")), [])
        self.assertEqual(load_registry()["task_id"], json.loads(task_path().read_text())["task_id"])
