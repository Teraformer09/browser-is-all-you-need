import unittest

from uber_clone_031 import load_environment
from uber_clone_031.harness.prompts import SYSTEM_PROMPT
from uber_clone_031.cli import parse_action, public_observation


class IntegrationContractTests(unittest.TestCase):
    def test_single_task_and_prompt(self):
        env = load_environment(max_examples=99)
        self.assertEqual(len(env.eval_dataset), 1)
        self.assertEqual(env.task.task_id, "uber_clone_031")
        self.assertEqual(env.max_turns, 12)
        self.assertEqual(env.eval_dataset[0]["prompt"][0]["content"], SYSTEM_PROMPT)

    def test_hidden_state_not_in_model_observation(self):
        obs = public_observation({"goal":"visible goal", "ui":[], "expected_state":{"secret":1},
            "apk_state":{"secret":2}, "reward_components":{"secret":3}, "scorecard":{"secret":4}})
        self.assertNotIn("secret", str(obs))
        self.assertNotIn("expected_state", obs)

    def test_action_parser_does_not_repair_targets(self):
        self.assertEqual(parse_action('{"type":"tap_element","element_id":"wrong_target"}')["element_id"], "wrong_target")
        self.assertEqual(parse_action("not json"), "not json")


if __name__ == "__main__":
    unittest.main()
