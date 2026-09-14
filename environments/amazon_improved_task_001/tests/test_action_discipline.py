"""V15 actor-discipline policy: rejected actions, duplicates, finish spam, focus taps."""
import json
import unittest

from amazon_improved_task_001.verification.generic.interaction import generic_check


def context(actions, rejected=()):
    """Minimal synthetic episode history; rejected holds 1-based steps that failed acceptance."""
    transitions = []
    frames = [{"index": 0, "stable": True, "errors": []}]
    for i, action in enumerate(actions, 1):
        transitions.append({
            "step": i, "action": action, "raw_response": json.dumps(action),
            "receipt": {"requested_action": action, "executed": True,
                        "accepted": i not in rejected, "failure_origin": "agent" if i in rejected else "none"},
            "trace_start": 0, "trace_end": 0,
        })
        frames.append({"index": i, "stable": True, "errors": []})
    return {"frames": frames, "transitions": transitions, "adb_trace": [], "task": {"max_steps": 18}}


TAP_SEARCH = {"type": "tap_element", "element_id": "search_input"}
TYPE_A = {"type": "type_text", "element_id": "search_input", "text": "Nimbus Wireless Headphones"}
ADD_A = {"type": "tap_element", "element_id": "add_DC001"}


class ActionDisciplineTests(unittest.TestCase):
    def check(self, actions, rejected=()):
        return generic_check(context(actions, rejected), "V15", "action_records")

    def test_clean_trajectory_passes(self):
        self.assertTrue(self.check([TYPE_A, {"type": "tap_element", "element_id": "search_button"},
                                    ADD_A, {"type": "finish"}]))

    def test_focus_tap_before_typing_fails(self):
        self.assertFalse(self.check([TAP_SEARCH, TYPE_A, ADD_A, {"type": "finish"}]))

    def test_rejected_action_fails(self):
        self.assertFalse(self.check([TYPE_A, ADD_A, {"type": "finish"}], rejected=(1,)))

    def test_consecutive_duplicates_fail(self):
        self.assertFalse(self.check([TYPE_A, ADD_A, ADD_A, {"type": "finish"}]))

    def test_finish_spam_fails(self):
        self.assertFalse(self.check([TYPE_A, {"type": "finish"}, {"type": "finish"}]))

    def test_all_five_methods_registered(self):
        from amazon_improved_task_001.verification.registry import VERIFIERS
        names = [n for n in VERIFIERS if n.startswith("verify_V15_")]
        self.assertEqual(len(names), 5)
        self.assertEqual(len({id(VERIFIERS[n][1]) for n in names}), 5)


if __name__ == "__main__":
    unittest.main()
