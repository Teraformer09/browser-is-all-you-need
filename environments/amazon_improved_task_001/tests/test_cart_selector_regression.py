"""Cart IDs remain unique with both real detail-page navigation controls visible."""
import copy
from pathlib import Path
import unittest

from amazon_improved_task_001.harness.peach import CART_TARGETS, permission_error, target_node, ui_nodes
from amazon_improved_task_001.verification.peach import acceptance
from test_peach_profile import EPISODE, fixture


class CartSelectorTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent / "fixtures/peach_detail_cart_controls.xml"
        self.xml = path.read_bytes()
        self.nodes = ui_nodes(self.xml, [])

    def test_both_recorded_controls_are_unique_and_permitted(self):
        self.assertEqual({n["id"] for n in self.nodes}, CART_TARGETS)
        for target in sorted(CART_TARGETS):
            action = {"type": "tap_element", "element_id": target}
            self.assertIsNone(permission_error(action))
            node = target_node(action, self.nodes)
            self.assertEqual(node["description"], "Go to cart" if target == "detail_cart_button" else "Cart tab, 3 items")
            self.assertEqual(target_node(action, ui_nodes(self.xml, [])), node)

    def test_genuinely_duplicated_cart_control_still_rejected(self):
        for node in self.nodes:
            action = {"type": "tap_element", "element_id": node["id"]}
            with self.assertRaisesRegex(ValueError, "exactly one"):
                target_node(action, [node, copy.deepcopy(node)])

    def test_cart_target_must_remain_enabled_and_visible(self):
        for target in CART_TARGETS:
            action = {"type": "tap_element", "element_id": target}
            for edit in ({"enabled": False}, {"clickable": False}, {"bounds": [0, 0, 0, 0]}):
                nodes = [{**n, **edit} if n["id"] == target else n for n in self.nodes]
                with self.assertRaises(ValueError):
                    target_node(action, nodes)

    def test_both_cart_controls_require_real_cart_state(self):
        cart = {"tables": fixture(), "episode_id": EPISODE}
        detail = copy.deepcopy(cart)
        detail["tables"]["eval_session"][0]["page"] = "detail"
        import json
        event = detail["tables"]["eval_events"][-1]
        payload = json.loads(event["payload"])
        payload["page"] = "detail"
        event["payload"] = json.dumps(payload)
        for target in CART_TARGETS:
            action = {"type": "tap_element", "element_id": target}
            self.assertTrue(acceptance(action, detail, cart))
            self.assertFalse(acceptance(action, detail, detail))

    def test_non_task_cart_alias_not_allowed(self):
        self.assertIsNotNone(permission_error({"type": "tap_element", "element_id": "checkout_button"}))


if __name__ == "__main__":
    unittest.main()
