"""OpenAI Responses API policy for structured Android actions."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from android_adk_rl_env.apk_env import ApkAction
from android_adk_rl_env.config import get_openai_api_key

OPENAI_API_URL = "https://api.openai.com/v1/responses"

SYSTEM_INSTRUCTIONS = """You control a real Android app through structured JSON actions.
Choose exactly one next action that moves toward the goal.
Allowed actions:
- type_text: requires element_id and text
- tap_element: requires element_id
- tap_coordinates: requires x and y
- press_back: no target or text
- press_home: no target or text
- swipe: requires x1, y1, x2, y2, duration_ms
- wait: no target or text
- finish: use only after final_reward is 1.0
For Dummy RL App, follow this priority exactly:
1. If reward_components.query is false, type expected_state.query into search_input.
2. If search_input has the expected query and search_result is still none, click search_button.
3. If reward_components.name is false, type expected_state.name into name_input.
4. If reward_components.email is false, type expected_state.email into email_input.
5. If reward_components.submitted is false after query/name/email are filled, click submit_button.
6. Use finish only when final_reward is 1.0.
If last_error says finish was premature, choose the missing click/input action instead.
Only use resource IDs visible in the observation. Return JSON only."""

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["tap_element", "tap_coordinates", "type_text", "press_back", "press_home", "swipe", "wait", "finish"],
        },
        "element_id": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "text": {
            "anyOf": [
                {"type": "string"},
                {"type": "null"},
            ]
        },
        "x": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "y": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "x1": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "y1": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "x2": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "y2": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "duration_ms": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["type", "element_id", "text", "x", "y", "x1", "y1", "x2", "y2", "duration_ms"],
}


class OpenAIActionPolicy:
    """Policy that asks an OpenAI model for the next structured APK action."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        api_url: str = OPENAI_API_URL,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.api_key = api_key or get_openai_api_key()
        self.api_url = api_url
        self.timeout = timeout
        self._last_metadata: dict[str, Any] = {}
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --policy openai")

    def reset(self) -> None:
        self._last_metadata = {}
        return None

    def act(self, observation: dict[str, Any]) -> ApkAction:
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {
                    "role": "user",
                    "content": "Observation JSON:\n" + json.dumps(self._compact_observation(observation), sort_keys=True),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "android_action",
                    "strict": True,
                    "schema": ACTION_SCHEMA,
                }
            },
        }
        response = self._post_json(payload)
        self._last_metadata = self._response_metadata(response)
        action_json = self._extract_text(response)
        try:
            action = json.loads(action_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI response was not valid action JSON: {action_json}") from exc
        return ApkAction.from_dict(action)

    def get_last_metadata(self) -> dict[str, Any]:
        return dict(self._last_metadata)

    def _compact_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        reward_components = observation.get("reward_components") or {}
        ui = observation.get("ui", [])
        return {
            "goal": observation.get("goal"),
            "steps": observation.get("steps"),
            "max_steps": observation.get("max_steps"),
            "valid_targets": [node.get("id") for node in ui if node.get("id")],
            "missing_reward_components": [
                name for name, passed in reward_components.items() if not passed
            ],
            "ui": ui,
            "last_action": observation.get("last_action"),
            "last_error": observation.get("last_error"),
            "expected_state": observation.get("expected_state"),
            "reward_components": reward_components,
            "final_reward": observation.get("final_reward"),
        }

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc

    def _extract_text(self, response: dict[str, Any]) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                    return content["text"]
        raise RuntimeError(f"OpenAI response did not contain output text: {response}")

    def _response_metadata(self, response: dict[str, Any]) -> dict[str, Any]:
        usage = response.get("usage", {}) if isinstance(response.get("usage"), dict) else {}
        return {
            "model": response.get("model", self.model),
            "response_id": response.get("id"),
            "prompt_tokens": int(usage.get("input_tokens", 0) or 0),
            "completion_tokens": int(usage.get("output_tokens", 0) or 0),
            "reasoning_tokens": int(usage.get("reasoning_tokens", 0) or 0),
        }
