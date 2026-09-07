"""Result export regressions; no network, credentials, Android or model calls."""
import base64
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from amazon_cart_001.integrations.legacy_scripted import digest, image_hashes, inside, prepare, verify_remote

PNG = b"\x89PNG\r\n\x1a\nunit-test-placeholder"
HASH = digest(PNG)
IMAGE = {"role": "user", "content": [
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(PNG).decode()}}
]}


class UploadResultTests(unittest.TestCase):
    def sample(self):
        return {"reward": 1, "prompt": [copy.deepcopy(IMAGE)], "completion": [],
                "info": {"evidence_images": [{"step": 0, "sha256": HASH}],
                         "saved_logs": {"verdict.json": '{"status":"PASS","reward":1}'},
                         "actor_type": "scripted-ui-validation",
                         "model_calls": 0, "training_eligible": False}}

    def metadata(self):
        return {"task_id": "amazon_cart_001", "policy": "scripted-ui-validation",
                "model_calls": 0, "training_eligible": False, "error": None,
                "actor_actions": 10, "screenshots": 11}

    def test_inline_png_digest(self):
        self.assertEqual(image_hashes(IMAGE), [HASH])

    def test_server_artifact_reference(self):
        self.assertEqual(image_hashes({"type": "artifact", "media_type": "image/png",
                                      "key": "images/" + HASH + ".png"}), [HASH])

    def test_json_encoded_messages(self):
        import json
        self.assertEqual(image_hashes(json.dumps([IMAGE])), [HASH])

    def test_original_images_and_logs_roundtrip(self):
        sample = self.sample()
        result = verify_remote({"samples": [copy.deepcopy(sample)]}, sample)
        for key in ("screenshots_verified", "logs_verified", "reward_verified", "scripted_label_verified"):
            self.assertTrue(result[key])
        self.assertFalse(result["browser_rendering_verified"])

    def test_missing_screenshot_rejected(self):
        sample = self.sample()
        remote = copy.deepcopy(sample)
        remote["prompt"] = []
        self.assertFalse(verify_remote({"samples": [remote]}, sample)["screenshots_verified"])

    def test_duplicate_screenshot_rejected(self):
        sample = self.sample()
        remote = copy.deepcopy(sample)
        remote["completion"] = [copy.deepcopy(IMAGE)]
        self.assertFalse(verify_remote({"samples": [remote]}, sample)["screenshots_verified"])

    def test_changed_log_rejected(self):
        sample = self.sample()
        remote = copy.deepcopy(sample)
        remote["info"]["saved_logs"]["verdict.json"] = "changed"
        self.assertFalse(verify_remote({"samples": [remote]}, sample)["logs_verified"])

    def test_changed_reward_rejected(self):
        sample = self.sample()
        remote = copy.deepcopy(sample)
        remote["reward"] = -1
        self.assertFalse(verify_remote({"samples": [remote]}, sample)["reward_verified"])

    def test_model_label_cannot_replace_scripted(self):
        sample = self.sample()
        remote = copy.deepcopy(sample)
        remote["info"]["actor_type"] = "openrouter"
        self.assertFalse(verify_remote({"samples": [remote]}, sample)["scripted_label_verified"])

    def test_duplicate_remote_samples_rejected(self):
        sample = self.sample()
        with self.assertRaises(ValueError):
            verify_remote({"samples": [sample, sample]}, sample)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            inside(Path("/tmp/cart-unit-root"), "../outside")

    def test_model_run_not_accepted_by_scripted_exporter(self):
        meta = self.metadata()
        meta["model_calls"] = 1
        with patch("amazon_cart_001.integrations.legacy_scripted.read_json", return_value=meta):
            with self.assertRaisesRegex(ValueError, "relabel"):
                prepare("/tmp/cart-unit-not-created")

    def test_training_eligible_record_rejected(self):
        meta = self.metadata()
        meta["training_eligible"] = True
        with patch("amazon_cart_001.integrations.legacy_scripted.read_json", return_value=meta):
            with self.assertRaisesRegex(ValueError, "relabel"):
                prepare("/tmp/cart-unit-not-created")

    def test_incomplete_action_count_rejected(self):
        meta = self.metadata()
        meta["actor_actions"] = 9
        with patch("amazon_cart_001.integrations.legacy_scripted.read_json", return_value=meta):
            with self.assertRaisesRegex(ValueError, "complete"):
                prepare("/tmp/cart-unit-not-created")

    def test_wrong_task_rejected(self):
        meta = self.metadata()
        meta["task_id"] = "payment_transfer_001"
        with patch("amazon_cart_001.integrations.legacy_scripted.read_json", return_value=meta):
            with self.assertRaisesRegex(ValueError, "DemoCart"):
                prepare("/tmp/cart-unit-not-created")


if __name__ == "__main__":
    unittest.main()
