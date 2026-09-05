"""Package layout and canonical-task checks; no emulator or model requests."""
import json
from pathlib import Path
import unittest
from uber_clone_031.cli import task_path
from uber_clone_031.verification.registry import load_registry

class LayoutTests(unittest.TestCase):
    def test_role_files_exist(self):
        root = task_path().parents[1]
        for role in ("cli.py", "harness/actions.py", "harness/device.py", "harness/episode.py",
                     "harness/evidence.py", "harness/prompts.py", "verification/registry.py",
                     "verification/scoring.py", "verification/task_checks.py", "verification/progress.py",
                     "integrations/prime_env.py", "integrations/prime_upload.py", "specs/policies.json", "specs/scoring.json"):
            with self.subTest(role=role):
                self.assertTrue((root / role).is_file())

    def test_one_canonical_task(self):
        source = json.loads(task_path().read_text())
        registry = load_registry()
        self.assertEqual(source["parameters"]["payment"], registry["task"]["expected"]["payment_method"])
        self.assertEqual(source["parameters"]["selected_ride"], registry["task"]["expected"]["cab_type"])
        self.assertNotIn("expected", source["verifier_contract"])
        self.assertFalse((task_path().parents[2] / "task/uber_clone_031.yaml").exists())

    def test_no_global_runtime_package(self):
        self.assertFalse((task_path().parents[2] / "runtime").exists())
        self.assertTrue((task_path().parents[1] / "harness/backend/apk_env.py").is_file())
