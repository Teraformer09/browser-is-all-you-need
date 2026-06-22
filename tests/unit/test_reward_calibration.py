import unittest

from android_adk_rl_env.benchmarking.reward_stats import check_reward_calibration, summarize_reward_distributions


class RewardCalibrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.thresholds = {"task_a": 1.0, "task_b": 1.0}

    def test_reward_summary_reports_best_of_k(self) -> None:
        summary = summarize_reward_distributions(
            {
                "task_a": [0.0, 0.5, 1.0],
                "task_b": [0.2, 0.7, 1.0],
            },
            thresholds=self.thresholds,
            k_values=[1, 2, 3],
            bootstrap_samples=10,
            bootstrap_seed=4,
        )
        self.assertIn("best_of_1", summary["aggregate"]["best_of_k"])
        self.assertIn("best_of_2", summary["aggregate"]["best_of_k"])
        self.assertGreaterEqual(
            summary["aggregate"]["best_of_k"]["best_of_3"]["mean"],
            summary["aggregate"]["best_of_k"]["best_of_1"]["mean"],
        )

    def test_reward_calibration_passes_for_good_vs_bad_policy_gap(self) -> None:
        report = check_reward_calibration(
            good_policy_rewards={
                "task_a": [1.0] * 10,
                "task_b": [1.0] * 10,
            },
            bad_policy_rewards={
                "task_a": [0.0] * 10,
                "task_b": [0.0] * 10,
            },
            thresholds=self.thresholds,
            bootstrap_samples=50,
            bootstrap_seed=7,
        )
        self.assertTrue(report["passes"])

    def test_reward_calibration_fails_when_bad_policy_is_too_good(self) -> None:
        report = check_reward_calibration(
            good_policy_rewards={
                "task_a": [1.0] * 10,
                "task_b": [1.0] * 10,
            },
            bad_policy_rewards={
                "task_a": [1.0] * 10,
                "task_b": [1.0] * 10,
            },
            thresholds=self.thresholds,
            bootstrap_samples=50,
            bootstrap_seed=7,
        )
        self.assertFalse(report["passes"])


if __name__ == "__main__":
    unittest.main()
