import os
import unittest

from android_adk_rl_env.runner import run_task


@unittest.skipUnless(os.environ.get("RUN_ADB_INTEGRATION") == "1", "set RUN_ADB_INTEGRATION=1 with an emulator/device")
class AdbDummyApkIntegrationTest(unittest.TestCase):
    def test_adb_dummy_apk(self) -> None:
        result = run_task("dummy_apk", "adb-scripted")
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
