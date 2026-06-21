import os
import unittest

from android_adk_rl_env.reset_manager import reset_task_device
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from tests.support.mock_adb_device import MockAdbDevice


class ResetManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_mode = os.environ.get("RESET_MODE")
        self.old_snapshot = os.environ.get("ADB_BASELINE_SNAPSHOT")
        os.environ["ADB_BASELINE_SNAPSHOT"] = "unit-test-snapshot"

    def tearDown(self) -> None:
        if self.old_mode is None:
            os.environ.pop("RESET_MODE", None)
        else:
            os.environ["RESET_MODE"] = self.old_mode
        if self.old_snapshot is None:
            os.environ.pop("ADB_BASELINE_SNAPSHOT", None)
        else:
            os.environ["ADB_BASELINE_SNAPSHOT"] = self.old_snapshot

    def test_snapshot_mode_creates_baseline_then_uses_it(self) -> None:
        os.environ["RESET_MODE"] = "snapshot"
        task = DummyApkFormSearchTask()
        device = MockAdbDevice(task)

        first = reset_task_device(task, device)
        second = reset_task_device(task.new_episode(), device)

        self.assertEqual(first.applied_mode, "full")
        self.assertTrue(device.snapshot_exists("unit-test-snapshot"))
        self.assertEqual(second.applied_mode, "snapshot")

    def test_snapshot_restore_falls_back_to_full_reset(self) -> None:
        os.environ["RESET_MODE"] = "snapshot"
        task = DummyApkFormSearchTask()
        device = MockAdbDevice(task)
        reset_task_device(task, device)
        device.fail_snapshot_restore = True

        metadata = reset_task_device(task.new_episode(), device)

        self.assertEqual(metadata.applied_mode, "full")
        self.assertTrue(metadata.fallback_used)


if __name__ == "__main__":
    unittest.main()
