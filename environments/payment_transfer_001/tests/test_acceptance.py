import unittest
from payment_transfer_001.harness.acceptance import assess_acceptance

class AcceptanceTests(unittest.TestCase):
    def before(self):
        return {"state":{"events":[],"amount_input":"","note":""}}
    def after(self,target="amount_input",focused=True):
        return {"state":{"events":[],"amount_input":"","note":""},
                "ui":[{"id":target,"focused":focused}]}
    def test_focus_tap_is_not_a_text_edit(self):
        r=assess_acceptance({"type":"tap_element","element_id":"amount_input"},self.before(),self.after())
        self.assertTrue(r["accepted"])
        self.assertIsNone(r["error"])
    def test_note_focus_without_mutation_is_valid(self):
        self.assertTrue(assess_acceptance({"type":"tap_element","element_id":"note_input"},
            self.before(),self.after("note_input"))["accepted"])
    def test_unproven_focus_is_pipeline_not_agent(self):
        r=assess_acceptance({"type":"tap_element","element_id":"amount_input"},self.before(),self.after(focused=False))
        self.assertIsNone(r["accepted"])
        self.assertEqual(r["failure_origin"],"pipeline")
    def test_noop_text_replacement_is_valid(self):
        after=self.after();after["state"]["note"]="Lunch"
        self.assertTrue(assess_acceptance({"type":"type_text","element_id":"note_input","text":"Lunch"},
            self.before(),after)["accepted"])
    def test_wrong_text_effect_is_unassessable(self):
        r=assess_acceptance({"type":"type_text","element_id":"note_input","text":"Lunch"},
            self.before(),self.after())
        self.assertEqual(r["failure_origin"],"pipeline")
    def test_explicit_rejection_stays_agent_failure(self):
        after=self.after();after["state"]["events"]=[{"action":"review","accepted":False,"error":"Missing account"}]
        r=assess_acceptance({"type":"tap_element","element_id":"review_button"},self.before(),after)
        self.assertFalse(r["accepted"]);self.assertEqual(r["failure_origin"],"agent")
    def test_missing_commit_receipt_not_silent_success(self):
        r=assess_acceptance({"type":"tap_element","element_id":"confirm_transfer_button"},self.before(),self.after())
        self.assertIsNone(r["accepted"]);self.assertEqual(r["failure_origin"],"pipeline")
