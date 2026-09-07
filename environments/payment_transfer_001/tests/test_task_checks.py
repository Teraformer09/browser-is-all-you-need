import copy
import json
from pathlib import Path
import unittest
from payment_transfer_001.verification.records import verify

TASK = json.loads((Path(__file__).parents[1] / "payment_transfer_001/specs/task.json").read_text())
def fixture():
    tx = {**TASK["expected"], "transaction_id":"receipt-1", "episode_id":"test",
          "status":"COMPLETED", "simulated":True, "reviewed_revision":4}
    return {**TASK["expected"], "schema_version":1, "episode_id":"test", "status":"COMPLETED",
            "simulated":True, "revision":4, "reviewed_revision":4, "transactions":[tx]}

class PaymentVerifierTests(unittest.TestCase):
    def test_correct(self):
        self.assertEqual(verify(fixture(), TASK, "test")["reward"], 1)
    def test_every_wrong_committed_field_fails(self):
        for key in TASK["expected"]:
            with self.subTest(key=key):
                data = fixture()
                data["transactions"][0][key] = 1 if key == "amount_paise" else "wrong"
                self.assertEqual(verify(data, TASK, "test")["reward"], -1)
    def test_success_label_is_not_enough(self):
        data = fixture(); data["transactions"] = []
        self.assertEqual(verify(data, TASK, "test")["reward"], -1)
    def test_duplicates(self):
        data = fixture(); data["transactions"] *= 2
        self.assertEqual(verify(data, TASK, "test")["reward"], -1)
    def test_stale_episode(self):
        self.assertEqual(verify(fixture(), TASK, "other")["status"], "INVALID")
    def test_corrupt_and_missing_state(self):
        for data in (None, {}, [], {"schema_version":1}):
            self.assertEqual(verify(data, TASK, "test")["reward"], 0)
    def test_review_revision(self):
        data = fixture(); data["reviewed_revision"] = 3
        self.assertEqual(verify(data, TASK, "test")["reward"], -1)
    def test_boolean_amount_not_money(self):
        data = fixture(); data["transactions"][0]["amount_paise"] = True
        self.assertEqual(verify(data, TASK, "test")["status"], "INVALID")
    def test_missing_task_parameter(self):
        task = copy.deepcopy(TASK); del task["expected"]["note"]
        self.assertEqual(verify(fixture(), task, "test")["status"], "INVALID")
    def test_no_real_transfer(self):
        data = fixture(); data["transactions"][0]["simulated"] = False
        self.assertEqual(verify(data, TASK, "test")["reward"], -1)
    def test_input_not_modified(self):
        data = fixture(); before = copy.deepcopy(data)
        verify(data, TASK, "test")
        self.assertEqual(data, before)

if __name__ == "__main__": unittest.main()
