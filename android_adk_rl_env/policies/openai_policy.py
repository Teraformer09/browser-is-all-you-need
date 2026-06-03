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
- input_resource: requires target and text
- click_resource: requires target
- press_back: no target or text
- wait: no target or text
- finish: use only after final_reward is 1.0
For Dummy RL App, follow this priority exactly:
1. If reward_components.query is false, input expected_state.query into search_input.
2. If search_input has the expected query and search_result is still none, click search_button.
3. If reward_components.name is false, input expected_state.name into name_input.
4. If reward_components.email is false, input expected_state.email into email_input.
5. If reward_components.submitted is false after query/name/email are filled, click submit_button.
6. Use finish only when final_reward is 1.0.
If last_error says finish was premature, choose the missing click/input action instead.
Only use resource IDs visible in the observation. Return JSON only."""

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": ["click_resource", "input_resource", "press_back", "wait", "finish"],
        },
        "target": {
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
    },
    "required": ["action", "target", "text"],
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
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --policy openai")

    def reset(self) -> None:
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
        action_json = self._extract_text(response)
        try:
            action = json.loads(action_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI response was not valid action JSON: {action_json}") from exc
        return ApkAction.from_dict(action)

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
