import unittest

from environments.mobile_android_rl.mobile_android_rl.taskset import load_taskset


class TaskLoaderTest(unittest.TestCase):
    def test_form_and_ride_tasksets_load_without_adb(self) -> None:
        self.assertEqual(len(load_taskset(split="train", app="form")), 25)
        self.assertEqual(len(load_taskset(split="eval", app="form")), 25)
        self.assertEqual(len(load_taskset(split="eval_randomized", app="form")), 5)
        self.assertEqual(len(load_taskset(split="train", app="ride")), 25)
        self.assertEqual(len(load_taskset(split="eval", app="ride")), 25)

    def test_loaded_tasks_have_competitor_alignment_fields(self) -> None:
        task = load_taskset(split="eval", app="form").tasks[0]
        self.assertEqual(task.surface, "android_apk")
        self.assertEqual(task.difficulty, "easy")
        self.assertEqual(task.split, "eval")
        self.assertIn("screen", task.expected_state)
        self.assertIn("enabled", task.randomization)
        self.assertIn("forbid_payment", task.safety)
        self.assertIn("episode_match", task.reward_weights)


if __name__ == "__main__":
    unittest.main()
