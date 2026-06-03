import unittest

from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.openai_finetune import examples_from_rollouts, scripted_bootstrap_examples
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.rollout import run_rollouts
from android_adk_rl_env.training.local_rl import (
    CandidateActionSpace,
    RlTrainConfig,
    evaluate_policy,
    state_key,
    summarize_episodes,
    train_policy,
)


class FakeAdbDevice:
    def __init__(self) -> None:
        self.task = DummyApkFormSearchTask()
        self.reset_state()

    def reset_state(self) -> None:
        self.query = ""
        self.name = ""
        self.email = ""
        self.submitted = False
        self.focus = None

    def wait_for_device(self) -> None:
        pass

    def clear_app_data(self) -> None:
        self.reset_state()

    def launch_app(self) -> None:
        pass

    def click_resource(self, resource_name: str) -> None:
        if resource_name in {"search_input", "name_input", "email_input"}:
            self.focus = resource_name
        elif resource_name == "submit_button":
            self.submitted = bool(self.name and self.email)

    def input_resource(self, resource_name: str, text: str) -> None:
        self.focus = resource_name
        if resource_name == "search_input":
            self.query = text
        elif resource_name == "name_input":
            self.name = text
        elif resource_name == "email_input":
            self.email = text

    def press_back(self) -> None:
        self.focus = None

    def dump_resource_nodes(self, resource_names: tuple[str, ...]) -> list[dict[str, object]]:
        values = {
            "search_input": self.query,
            "name_input": self.name,
            "email_input": self.email,
            "status_text": "Submitted" if self.submitted else "Status: waiting",
        }
        return [
            {
                "id": name,
                "resource_id": f"{self.task.package}:id/{name}",
                "text": values.get(name, ""),
                "focused": self.focus == name,
                "bounds": [0, 0, 10, 10],
                "center": [5, 5],
            }
            for name in resource_names
        ]

    def read_shared_prefs(self) -> str:
        if not (self.query or self.name or self.email or self.submitted):
            return ""
        submitted = "true" if self.submitted else "false"
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\" ?>\n"
            "<map>\n"
            f"    <boolean name=\"submitted\" value=\"{submitted}\" />\n"
            f"    <string name=\"query\">{self.query}</string>\n"
            f"    <string name=\"name\">{self.name}</string>\n"
            f"    <string name=\"email\">{self.email}</string>\n"
            "</map>\n"
        )


class DummyApkTrainingTest(unittest.TestCase):
    def test_step_env_completes_with_scripted_policy(self) -> None:
        task = DummyApkFormSearchTask()

        def env_factory() -> DummyApkEnv:
            return DummyApkEnv(task=task, device=FakeAdbDevice())

        rollouts = run_rollouts(env_factory, lambda: ScriptedApkPolicy(task), episodes=1)

        self.assertTrue(rollouts[0]["success"])
        self.assertEqual(rollouts[0]["final_reward"], 1.0)
        self.assertGreaterEqual(len(rollouts[0]["transitions"]), 6)

    def test_invalid_action_is_reported(self) -> None:
        env = DummyApkEnv(device=FakeAdbDevice())
        env.reset()

        result = env.step(ApkAction("click_resource", target="missing"))

        self.assertEqual(result.reward, 0.0)
        self.assertTrue(result.info["invalid_action"])
        self.assertIn("unsupported target", result.info["error"])

    def test_sft_examples_from_rollout(self) -> None:
        task = DummyApkFormSearchTask()
        rollouts = run_rollouts(
            lambda: DummyApkEnv(task=task, device=FakeAdbDevice()),
            lambda: ScriptedApkPolicy(task),
            episodes=1,
        )

        examples = examples_from_rollouts(rollouts)

        self.assertGreaterEqual(len(examples), 6)
        self.assertIn("messages", examples[0])
        self.assertEqual(examples[0]["messages"][-1]["role"], "assistant")

    def test_scripted_bootstrap_examples_do_not_need_adb(self) -> None:
        examples = scripted_bootstrap_examples()

        self.assertEqual(len(examples), 6)
        self.assertIn("search_input", examples[0]["messages"][-1]["content"])

    def test_local_rl_trainer_updates_policy(self) -> None:
        task = DummyApkFormSearchTask(max_steps=8)

        def env_factory() -> DummyApkEnv:
            return DummyApkEnv(task=task, device=FakeAdbDevice(), max_steps=8)

        config = RlTrainConfig(episodes=3, max_steps=8, learning_rate=0.2, seed=11)
        action_space = CandidateActionSpace(task=task, include_distractors=False)
        policy, train_episodes = train_policy(env_factory, config, action_space=action_space)
        eval_episodes = evaluate_policy(env_factory, policy, episodes=1)

        self.assertEqual(len(train_episodes), 3)
        self.assertEqual(len(eval_episodes), 1)
        self.assertIn("success_rate", summarize_episodes(eval_episodes))
        self.assertGreater(len(policy.preferences), 0)

    def test_state_key_tracks_typed_fields(self) -> None:
        task = DummyApkFormSearchTask()
        env = DummyApkEnv(task=task, device=FakeAdbDevice())
        observation = env.reset()
        before = state_key(observation)
        after = env.step(ApkAction("input_resource", target="search_input", text=task.query)).observation

        self.assertNotEqual(before, state_key(after))


if __name__ == "__main__":
    unittest.main()
