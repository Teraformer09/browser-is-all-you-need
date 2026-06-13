import unittest

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.tasks.ride_booking import RideBookingTask
from tests.support.mock_adb_device import MockAdbDevice


class RideBookingTaskTest(unittest.TestCase):
    def test_ride_booking_exact_success(self) -> None:
        task = RideBookingTask()
        env = DummyApkEnv(task=task, device=MockAdbDevice(task=task), max_steps=task.max_steps)
        env.reset()
        for action in task.action_sequence():
            result = env.step(ApkAction.from_dict(action))
        self.assertTrue(result.observation["exact_success"])
        self.assertEqual(result.observation["final_reward"], 1.0)

    def test_ride_cancel_exact_success(self) -> None:
        task = RideBookingTask(cancel_after_assignment=True)
        env = DummyApkEnv(task=task, device=MockAdbDevice(task=task), max_steps=task.max_steps)
        env.reset()
        for action in task.action_sequence():
            result = env.step(ApkAction.from_dict(action))
        self.assertTrue(result.observation["exact_success"])
        self.assertEqual(result.observation["apk_state"]["ride_cancelled"], "true")


if __name__ == "__main__":
    unittest.main()
