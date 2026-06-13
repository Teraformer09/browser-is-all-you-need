import unittest

from android_adk_rl_env.android_world_bridge import android_world_status


class AndroidWorldMappingSmokeTest(unittest.TestCase):
    def test_androidworld_missing_or_present_is_reported(self) -> None:
        status = android_world_status()
        self.assertIsInstance(status.installed, bool)


if __name__ == "__main__":
    unittest.main()
