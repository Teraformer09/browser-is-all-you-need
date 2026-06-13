import unittest

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from tests.support.mock_adb_device import MockAdbDevice


class MockAdbDeviceTest(unittest.TestCase):
    def test_mock_device_completes_form_task(self) -> None:
        env = DummyApkEnv(device=MockAdbDevice())
        observation = env.reset()
        self.assertNotEqual(observation["episode_id"], "")
        for action in [
            ApkAction("input_resource", target="search_input", text="airport ride"),
            ApkAction("click_resource", target="search_button"),
            ApkAction("input_resource", target="name_input", text="Ada Lovelace"),
            ApkAction("input_resource", target="email_input", text="ada@example.com"),
            ApkAction("click_resource", target="submit_button"),
        ]:
            result = env.step(action)
        self.assertTrue(result.observation["exact_success"])
        self.assertEqual(result.observation["final_reward"], 1.0)


if __name__ == "__main__":
    unittest.main()
