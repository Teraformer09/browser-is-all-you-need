import unittest

from android_adk_rl_env.apk_env import DummyApkEnv
from tests.support.mock_adb_device import MockAdbDevice


class ResetLifecycleTest(unittest.TestCase):
    def test_reset_generates_new_episode_and_clears_state(self) -> None:
        env = DummyApkEnv(device=MockAdbDevice())
        first = env.reset()["episode_id"]
        env.step({"type": "type_text", "element_id": "search_input", "text": "airport ride"})
        second_observation = env.reset()
        self.assertNotEqual(first, second_observation["episode_id"])
        self.assertEqual(second_observation["final_reward"], 0.0)
        self.assertFalse(second_observation["exact_success"])


if __name__ == "__main__":
    unittest.main()
