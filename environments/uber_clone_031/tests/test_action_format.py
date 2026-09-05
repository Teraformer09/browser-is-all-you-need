"""The constrained API request describes syntax, never the task's answer."""
import json
import unittest

import jsonschema

from uber_clone_031.harness.actions import ACTION_SCHEMA, completion_payload

class ActionFormatTests(unittest.TestCase):
    def test_schema_itself_is_valid(self):
        jsonschema.Draft202012Validator.check_schema(ACTION_SCHEMA)

    def test_all_supported_actions(self):
        actions = [
            {"type": "tap_element", "element_id": "visible_id"},
            {"type": "type_text", "element_id": "visible_id", "text": "user text"},
            {"type": "press_back"}, {"type": "wait"}, {"type": "finish"},
            {"type": "swipe", "x1": 1, "y1": 2, "x2": 3, "y2": 4, "duration_ms": 400},
        ]
        for action in actions:
            with self.subTest(action=action):
                jsonschema.validate(action, ACTION_SCHEMA)

    def test_forbidden_argument_combinations(self):
        for action in [
            {"type": "press_back", "element_id": "field"},
            {"type": "tap_element", "element_id": "field", "text": "unneeded"},
            {"type": "type_text", "element_id": "field"},
            {"type": "unknown"}, [], None, "prose before JSON",
        ]:
            with self.subTest(action=action):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(action, ACTION_SCHEMA)

    def test_text_mode_is_the_original_request(self):
        messages = [{"role": "user", "content": "goal"}]
        self.assertEqual(completion_payload("model:free", messages),
                         {"model": "model:free", "messages": messages, "max_tokens": 2048,
                          "temperature": 0, "stream": False})

    def test_strict_schema_requires_capable_provider(self):
        payload = completion_payload("model:free", [], "json_schema")
        self.assertEqual(payload["provider"], {"require_parameters": True})
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], ACTION_SCHEMA)

    def test_schema_does_not_contain_task_answers_or_an_oracle(self):
        serialized = json.dumps(ACTION_SCHEMA)
        for answer in ("Airport Road", "City Centre", "Premium", "payment_card", "pickup_input"):
            self.assertNotIn(answer, serialized)

    def test_request_cannot_mutate_registered_schema(self):
        payload = completion_payload("model:free", [], "json_schema")
        payload["response_format"]["json_schema"]["schema"]["anyOf"].clear()
        self.assertEqual(len(ACTION_SCHEMA["anyOf"]), 6)

    def test_json_object_only_constrains_json_syntax(self):
        payload = completion_payload("model:free", [], "json_object")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["provider"], {"require_parameters": True})
        self.assertNotIn("json_schema", payload["response_format"])

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            completion_payload("model:free", [], "healed")
