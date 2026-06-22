import unittest

from android_adk_rl_env.benchmarking.pass_at_k import compute_pass_at_k, summarize_pass_at_k, unbiased_pass_at_k


class PassAtKTest(unittest.TestCase):
    def test_unbiased_estimator_matches_known_case(self) -> None:
        self.assertAlmostEqual(unbiased_pass_at_k(n=10, c=1, k=1), 0.1)
        self.assertAlmostEqual(unbiased_pass_at_k(n=10, c=2, k=2), 1.0 - (28.0 / 45.0))

    def test_compute_pass_at_k_raises_when_k_exceeds_samples(self) -> None:
        with self.assertRaises(ValueError):
            compute_pass_at_k({"task_a": [True, False], "task_b": [False, False]}, [1, 3])

    def test_compute_pass_at_k_aggregates_over_tasks(self) -> None:
        summary = compute_pass_at_k(
            {
                "task_a": [True, False, False, False],
                "task_b": [True, True, False, False],
            },
            [1, 2],
        )
        self.assertAlmostEqual(summary["pass@1"], (0.25 + 0.5) / 2.0)
        self.assertGreater(summary["pass@2"], summary["pass@1"])

    def test_summary_includes_confidence_interval_shape(self) -> None:
        summary = summarize_pass_at_k(
            {"task_a": [True, False, False], "task_b": [True, True, False]},
            [1],
            bootstrap_samples=20,
            bootstrap_seed=3,
        )
        self.assertIn("pass@1", summary)
        self.assertIn("mean", summary["pass@1"])
        self.assertIn("p2_5", summary["pass@1"])
        self.assertIn("p97_5", summary["pass@1"])


if __name__ == "__main__":
    unittest.main()
