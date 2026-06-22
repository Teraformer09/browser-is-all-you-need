import unittest

from android_adk_rl_env.task_specs import build_known_task, load_task_spec


class TaskSpecTest(unittest.TestCase):
    def test_form_spec_loads_and_builds_known_task(self) -> None:
        spec = load_task_spec("tasks/form_default.yaml")
        task = build_known_task(spec)
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(spec.success.check, "dummy_form_exact")
        self.assertEqual(task.task_id, "form_default")
        self.assertEqual(task.query, "airport ride")

    def test_ride_spec_loads_with_fractional_reward_mode(self) -> None:
        spec = load_task_spec("tasks/ride_cheapest.yaml")
        self.assertEqual(spec.reward.mode, "fractional")
        self.assertEqual(spec.task_type, "ride_booking")


if __name__ == "__main__":
    unittest.main()
