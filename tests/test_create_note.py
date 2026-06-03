import unittest

from android_adk_rl_env.actions import Action
from android_adk_rl_env.env import AndroidAdkEnv
from android_adk_rl_env.runner import run_task
from android_adk_rl_env.tasks.create_note import CreateNoteTask
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


class CreateNoteTaskTest(unittest.TestCase):
    def test_scripted_policy_completes_task(self) -> None:
        result = run_task("create_note", "scripted")

        self.assertTrue(result["success"])
        self.assertEqual(result["reward"], 1.0)
        self.assertEqual(result["steps"], 6)

    def test_reward_requires_exact_note(self) -> None:
        task = CreateNoteTask()
        env = AndroidAdkEnv(task)
        env.reset()

        env.step(Action("open_app", target="notes"))
        env.step(Action("tap", target="new_note"))
        env.step(Action("input_text", text=task.title))
        env.step(Action("tap", target="body"))
        env.step(Action("input_text", text="wrong body"))
        result = env.step(Action("submit"))

        self.assertFalse(result.done)
        self.assertEqual(result.reward, 0.0)

    def test_invalid_action_reports_error(self) -> None:
        task = CreateNoteTask()
        env = AndroidAdkEnv(task)
        env.reset()

        result = env.step(Action("tap", target="new_note"))

        self.assertEqual(result.reward, 0.0)
        self.assertEqual(result.observation["last_error"], "no app open")

    def test_dummy_apk_reward_checks_durable_state(self) -> None:
        task = DummyApkFormSearchTask()
        prefs = """<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <boolean name="submitted" value="true" />
    <string name="query">airport ride</string>
    <string name="name">Ada Lovelace</string>
    <string name="email">ada@example.com</string>
</map>
"""

        self.assertEqual(task.reward_from_prefs(prefs), 1.0)
        self.assertEqual(task.reward_from_prefs(prefs.replace("true", "false")), 0.0)


if __name__ == "__main__":
    unittest.main()
