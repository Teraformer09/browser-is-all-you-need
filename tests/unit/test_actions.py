import unittest

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.core.actions import ActionValidationError, MobileAction
from tests.support.mock_adb_device import MockAdbDevice


class ActionSchemaTest(unittest.TestCase):
    def test_invalid_json_action(self) -> None:
        with self.assertRaises(ActionValidationError):
            MobileAction.parse_json("{")

    def test_unknown_action_type(self) -> None:
        with self.assertRaises(ActionValidationError):
            MobileAction.from_dict({"type": "launch_missiles"})

    def test_tap_missing_element_id(self) -> None:
        with self.assertRaises(ActionValidationError):
            MobileAction.from_dict({"type": "tap_element"})

    def test_type_without_text(self) -> None:
        with self.assertRaises(ActionValidationError):
            MobileAction.from_dict({"type": "type_text", "element_id": "name_input"})

    def test_swipe_missing_coordinates(self) -> None:
        with self.assertRaises(ActionValidationError):
            MobileAction.from_dict({"type": "swipe", "x1": 1})

    def test_action_does_not_crash_env(self) -> None:
        env = DummyApkEnv(device=MockAdbDevice())
        env.reset()
        result = env.step('{"type":"tap_element"}')
        self.assertEqual(result.reward, -0.05)
        self.assertFalse(result.done)
        self.assertEqual(result.info["error"], "invalid_action_schema")

    def test_tap_unknown_element_id(self) -> None:
        env = DummyApkEnv(device=MockAdbDevice())
        env.reset()
        result = env.step(ApkAction("click_resource", target="missing"))
        self.assertEqual(result.reward, -0.05)
        self.assertIn("tap_unknown_element_id", result.info["error"])


if __name__ == "__main__":
    unittest.main()
