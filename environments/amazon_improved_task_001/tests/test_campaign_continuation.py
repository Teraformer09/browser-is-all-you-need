"""Continuation keeps the first result counted and the original spending cap."""
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

from amazon_improved_task_001 import load_environment
from amazon_improved_task_001.integrations.campaign_budget import CampaignBudget, campaign_plan


class ContinuationTests(unittest.TestCase):
    def test_attempt_two_has_only_one_new_attempt_and_eighteen_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = CampaignBudget(9, directory, completed_attempts=1, attempts_this_run=1, prior_spend_usd=0.4409)
            receipt = budget.reserve_attempt()
            self.assertEqual(receipt["campaign_attempt_number"], 2)
            self.assertEqual(receipt["completed_attempts_before_run"], 1)
            with self.assertRaises(RuntimeError): budget.reserve_attempt()
            for _ in range(18): receipt = budget.reserve_call()
            self.assertEqual(Decimal(str(receipt["reserved_upper_bound_usd"])), Decimal("1.179812"))
            with self.assertRaises(RuntimeError): budget.reserve_call()

    def test_continuation_never_resets_the_twelve_attempt_limit(self):
        for completed, count in ((1,12), (11,2), (12,1), (-1,1), (True,1), (1,True), (1,0)):
            with self.assertRaises(ValueError): campaign_plan(9,completed,count)
        self.assertEqual(campaign_plan(9,11,1)["attempt_limit"],1)
        self.assertEqual(campaign_plan(9,1)["attempt_limit"],11)

    def test_previous_spend_is_not_refunded(self):
        with self.assertRaisesRegex(ValueError,"approved campaign cap"):
            campaign_plan(9,1,11,1)
        for prior in (True,-1,float("nan"),float("inf"),"0.4"):
            with self.assertRaises(ValueError): campaign_plan(9,1,1,prior)

    def test_loading_continuation_does_not_launch_or_create_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
                env=load_environment(capped_campaign=True,max_total_spend_usd=9,
                    completed_attempts=1,attempts_this_run=1,prior_spend_usd=0.4409,artifact_dir=directory)
                self.assertEqual(env.max_attempts,1)
                self.assertEqual(env.completed_attempts,1)
                self.assertFalse(env.allow_eval)
                self.assertIsNone(env.budget)
                self.assertFalse((Path(directory)/"campaign-budget.json").exists())
                session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
