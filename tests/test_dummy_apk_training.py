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
from tests.support.mock_adb_device import MockAdbDevice


class DummyApkTrainingTest(unittest.TestCase):
    def test_step_env_completes_with_scripted_policy(self) -> None:
        task = DummyApkFormSearchTask()

        def env_factory() -> DummyApkEnv:
            return DummyApkEnv(task=task, device=MockAdbDevice(task=task))

        rollouts = run_rollouts(env_factory, lambda: ScriptedApkPolicy(task), episodes=1)

        self.assertTrue(rollouts[0]["success"])
        self.assertEqual(rollouts[0]["final_reward"], 1.0)
        self.assertGreaterEqual(len(rollouts[0]["transitions"]), 6)

    def test_invalid_action_is_reported(self) -> None:
        env = DummyApkEnv(device=MockAdbDevice())
        env.reset()

        result = env.step(ApkAction("click_resource", target="missing"))

        self.assertEqual(result.reward, -0.05)
        self.assertTrue(result.info["invalid_action"])
        self.assertIn("tap_unknown_element_id", result.info["error"])

    def test_sft_examples_from_rollout(self) -> None:
        task = DummyApkFormSearchTask()
        rollouts = run_rollouts(
            lambda: DummyApkEnv(task=task, device=MockAdbDevice(task=task)),
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
            return DummyApkEnv(task=task, device=MockAdbDevice(task=task), max_steps=8)

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
        env = DummyApkEnv(task=task, device=MockAdbDevice(task=task))
        observation = env.reset()
        before = state_key(observation)
        after = env.step(ApkAction("input_resource", target="search_input", text=task.query)).observation

        self.assertNotEqual(before, state_key(after))


if __name__ == "__main__":
    unittest.main()
