import tempfile
import unittest
from unittest.mock import patch

from android_adk_rl_env.rollout_runner import run_rollout_suite
from tests.support.mock_adb_device import MockAdbDevice


class RolloutRunnerTest(unittest.TestCase):
    def test_rollout_runner_writes_artifacts_with_mock_adb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("android_adk_rl_env.rollout_runner.AdbDevice", MockAdbDevice):
                summary = run_rollout_suite(backend="adb", include_openai=False, artifact_root=tmp)
                self.assertEqual(summary["success_rate"], 1.0)
                self.assertEqual(summary["task_count"], 4)


if __name__ == "__main__":
    unittest.main()
