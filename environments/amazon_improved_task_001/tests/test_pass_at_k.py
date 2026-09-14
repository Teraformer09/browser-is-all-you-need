"""Arithmetic/reporting tests; these synthetic outcomes are NOT evaluation results."""
import copy
import unittest
from amazon_improved_task_001.verification.pass_at_k import estimate, summarize


def attempts(passes=4):
    return [dict(attempt_id=str(i), episode_id='peach_' + f'{i:032x}',
        rubric_sha256='a'*64, task_sha256='b'*64, actor_config_sha256='c'*64,
        campaign_sha256='d'*64, model='test-fixture-no-model',
        status='PASS' if i < passes else 'FAIL', reward=1 if i < passes else -1) for i in range(12)]


class PassAtKTests(unittest.TestCase):
    def test_exact_12_attempt_band(self):
        for passed, expected, met in ((4, 0.7454545454545455, True), (5, 0.8409090909090909, True),
                                      (6, 0.9090909090909091, False)):
            report = summarize(attempts(passed))
            self.assertAlmostEqual(report['pass_at_k'], expected)
            self.assertEqual(report['target_met'], met)
            self.assertEqual(len(report['attempts']), 12)

    def test_campaign_preserves_requested_gpt41_and_attempt_budget(self):
        import json
        from pathlib import Path
        from amazon_improved_task_001.verification.strict import SPEC
        campaign = json.loads((SPEC.parent / "campaign_12.json").read_text())
        self.assertEqual(campaign["model"], "openai/gpt-4.1")
        self.assertEqual(campaign["model_provider"], "prime")
        self.assertNotIn("api_base_url", campaign)
        self.assertNotIn("api_key_var", campaign)
        self.assertFalse(campaign["model_is_free"])
        self.assertFalse(campaign["reasoning_effort_supported"])
        self.assertNotIn("reasoning_effort", campaign["sampling_args"])
        self.assertEqual(campaign["rollouts_per_example"], 12)
        self.assertEqual(campaign["max_total_spend_usd"], 9)
        self.assertEqual(campaign["transport_retries"], 0)
        self.assertEqual(campaign["max_inference_requests"], 216)
        self.assertLess(campaign["listed_campaign_upper_bound_usd"], 9)

    def test_zero_and_all_success(self):
        self.assertEqual(estimate(12, 0), 0)
        self.assertEqual(estimate(12, 12), 1)

    def test_invalid_not_silently_dropped(self):
        rows = attempts()
        rows[-1].update(status='INVALID', reward=0)
        report = summarize(rows)
        self.assertEqual(report['counts']['INVALID'], 1)
        self.assertIsNone(report['pass_at_k'])
        self.assertAlmostEqual(report['pass_at_k_conditional_on_valid'], estimate(11, 4))
        self.assertAlmostEqual(report['operational_pass_at_k_invalid_as_non_success'], estimate(12, 4))
        self.assertIsNone(report['target_met'])

    def test_preboot_invalid_has_no_invented_episode(self):
        rows = attempts()
        rows[-1].update(status='INVALID', reward=0, episode_id=None, phase='setup', reason_codes=['KVM_UNAVAILABLE'])
        self.assertEqual(summarize(rows)['counts']['INVALID'], 1)
        rows[-1]['status'] = 'PASS'
        with self.assertRaises(ValueError): summarize(rows)

    def test_no_early_success_claim(self):
        report = summarize(attempts()[:5])
        self.assertFalse(report['complete'])
        self.assertIsNone(report['pass_at_k'])
        self.assertIsNone(report['target_met'])

    def test_no_outcome_based_extra_attempt(self):
        with self.assertRaises(ValueError): summarize(attempts() + [copy.deepcopy(attempts()[0])])

    def test_duplicate_and_mixed_contracts_rejected(self):
        for field, value in (('attempt_id','0'), ('episode_id','peach_'+'0'*32),
                             ('model','different'), ('rubric_sha256','e'*64),
                             ('task_sha256','e'*64), ('actor_config_sha256','e'*64),
                             ('campaign_sha256','e'*64)):
            rows = attempts()
            rows[-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): summarize(rows)

    def test_bad_arguments_rejected(self):
        for values in ((12, -1, 3), (12, 13, 3), (12, 4, 0), (12, 4, 13), (True, 0, 1)):
            with self.assertRaises(ValueError): estimate(*values)
        for rows in ([None], [42], {}):
            with self.assertRaises(ValueError): summarize(rows)
        for kwargs in ({'k':None}, {'k':True}, {'planned':'12'}, {'target':None}, {'target':[0.9, 0.7]}):
            with self.assertRaises(ValueError): summarize([], **kwargs)

    def test_status_reward_must_agree(self):
        rows = attempts()
        rows[0]['reward'] = -1
        with self.assertRaises(ValueError): summarize(rows)


if __name__ == '__main__':
    unittest.main()
