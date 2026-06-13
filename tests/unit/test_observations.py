import unittest

from android_adk_rl_env.core.observations import build_observation


class ObservationTest(unittest.TestCase):
    def test_compact_observation_has_required_fields(self) -> None:
        observation = build_observation(
            {
                "goal": "Fill the form",
                "screen": "form",
                "steps": 2,
                "max_steps": 10,
                "ui": [{"id": "submit_button", "text": "Submit", "class_name": "Button"}],
                "last_action": None,
                "last_error": None,
            }
        )
        for key in ["task", "screen", "step", "max_steps", "elements", "last_action", "last_error"]:
            self.assertIn(key, observation)
        self.assertEqual(observation["elements"][0]["element_id"], "submit_button")


if __name__ == "__main__":
    unittest.main()
