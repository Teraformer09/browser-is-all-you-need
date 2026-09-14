"""MiniMax M3 series: parameterized model/prices/cap; GPT-4.1 defaults stay frozen."""
import tempfile
import unittest
from decimal import Decimal

from amazon_improved_task_001.integrations.campaign_budget import (
    CampaignBudget, call_reserve, campaign_plan, valid_model,
    DEFAULT_INPUT_USD, DEFAULT_OUTPUT_USD, VM_RESERVE)

MM3 = "minimax/minimax-m3"
MM3_IN, MM3_OUT = 0.3, 1.2


class MiniMaxPlanTests(unittest.TestCase):
    def test_five_attempt_series_reservation(self):
        plan = campaign_plan(1.5, 0, 5, 0, input_usd=MM3_IN, output_usd=MM3_OUT, planned_attempts=5)
        reserve = call_reserve(MM3_IN, MM3_OUT)
        self.assertEqual(reserve, Decimal("0.0048576"))
        expected = 5 * VM_RESERVE + 5 * 18 * reserve
        self.assertEqual(plan["approved_run_upper_bound"], expected)
        self.assertLess(float(expected), 1.5)

    def test_defaults_remain_gpt41_twelve_attempts(self):
        plan = campaign_plan(9, 8, 1, 2.7412)
        self.assertEqual(plan["planned_attempts"], 12)
        self.assertEqual(call_reserve(), call_reserve(DEFAULT_INPUT_USD, DEFAULT_OUTPUT_USD))

    def test_cap_above_nine_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "USD 9"):
            campaign_plan(9.5, 0, 1, 0)

    def test_reservations_must_fit_the_smaller_cap(self):
        with self.assertRaisesRegex(ValueError, "approved campaign cap"):
            campaign_plan(1.0, 0, 5, 0, input_usd=MM3_IN, output_usd=MM3_OUT, planned_attempts=5)

    def test_model_slug_validation(self):
        self.assertEqual(valid_model(MM3), MM3)
        for bad in ("gpt 4.1", "UPPER/model", "no-slash", "", None, 3):
            with self.assertRaises(ValueError):
                valid_model(bad)

    def test_budget_records_series_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            budget = CampaignBudget(1.5, temp, completed_attempts=0, attempts_this_run=5,
                                    input_usd=MM3_IN, output_usd=MM3_OUT, planned_attempts=5, model=MM3)
            budget.reserve_attempt()
            state = budget.persist()
            self.assertEqual(state["campaign_model"], MM3)
            self.assertEqual(state["campaign_planned_attempts"], 5)
            self.assertEqual(state["campaign_attempt_number"], 1)
            self.assertEqual(state["cap_usd"], 1.5)

    def test_attempt_numbering_starts_at_one_for_new_series(self):
        with tempfile.TemporaryDirectory() as temp:
            budget = CampaignBudget(1.5, temp, attempts_this_run=5, planned_attempts=5, model=MM3,
                                    input_usd=MM3_IN, output_usd=MM3_OUT)
            for expected in range(1, 6):
                self.assertEqual(budget.reserve_attempt()["campaign_attempt_number"], expected)
            with self.assertRaises(RuntimeError):
                budget.reserve_attempt()


    def test_campaign_temperature_parameterized_and_default_frozen(self):
        from amazon_improved_task_001.integrations.prime_env import load_environment
        env = load_environment(capped_campaign=True, allow_eval=False, max_total_spend_usd=9,
                               campaign_temperature=0)
        self.assertEqual(env.campaign_temperature, 0)
        default_env = load_environment(capped_campaign=True, allow_eval=False, max_total_spend_usd=9)
        self.assertEqual(default_env.campaign_temperature, 0.6)
        for bad in (-0.1, 1.1, True, "0"):
            with self.assertRaises(ValueError):
                load_environment(capped_campaign=True, allow_eval=False, max_total_spend_usd=9,
                                 campaign_temperature=bad)


if __name__ == "__main__":
    unittest.main()
