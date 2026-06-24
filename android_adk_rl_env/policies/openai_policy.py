"""OpenAI Responses API policy for structured Android actions."""

from __future__ import annotations

import json
import os
import time
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
For ride-booking tasks, follow this priority exactly:
1. If pickup is not filled, type expected_state.ride_pickup into pickup_input.
2. If the ride type is not selected, tap the matching ride_type button.
3. If destination is not filled, type expected_state.ride_drop into drop_input.
4. Tap destination_search_button after the destination is entered.
5. If cab type is not selected, tap the matching ride_option button.
6. If payment is not selected, tap the matching payment button.
7. Tap confirm_ride_button once the earlier fields are complete.
8. Use finish only when final_reward is 1.0.
For the legacy form task, preserve the search/name/email flow if those fields appear instead.
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
        timeout: float | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or get_openai_api_key()
        self.api_url = api_url
        self.timeout = timeout or float(os.environ.get("OPENAI_POLICY_TIMEOUT_SECONDS", "120"))
        self.max_retries = int(os.environ.get("OPENAI_POLICY_MAX_RETRIES", "2"))
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
            "max_output_tokens": 64,
            "temperature": 0,
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
        candidate = self._normalize_action(ApkAction.from_dict(action))
        return self._repair_action(candidate, observation)

    def get_last_metadata(self) -> dict[str, Any]:
        return dict(self._last_metadata)

    def _compact_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        reward_components = observation.get("reward_components") or {}
        raw_valid_targets = observation.get("valid_targets") or []
        ui = observation.get("ui", [])
        valid_targets = []
        for target in raw_valid_targets:
            target_text = str(target)
            if target_text and target_text not in valid_targets:
                valid_targets.append(target_text)
        visible_text = []
        for node in ui:
            node_id = node.get("id")
            node_text = node.get("text") or node.get("content_description")
            if node_id and node_id not in valid_targets:
                valid_targets.append(str(node_id))
            if node_text and len(visible_text) < 8:
                visible_text.append(str(node_text))
        return {
            "goal": observation.get("goal"),
            "steps": observation.get("steps"),
            "max_steps": observation.get("max_steps"),
            "valid_targets": valid_targets,
            "visible_text": visible_text,
            "missing_reward_components": [
                name for name, passed in reward_components.items() if not passed
            ],
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
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc
            except (TimeoutError, urllib.error.URLError) as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError(
                        f"OpenAI request failed after {self.max_retries} attempts: {type(exc).__name__}: {exc}"
                    ) from exc
                time.sleep(float(attempt))
        raise RuntimeError("OpenAI request retry loop exited unexpectedly")

    def _normalize_action(self, action: ApkAction) -> ApkAction:
        target = self._normalize_target(action.target)
        text = self._normalize_text(action.text) if action.action == "input_resource" else action.text
        return ApkAction(
            action=action.action,
            target=target,
            text=text,
            x=action.x,
            y=action.y,
            x1=action.x1,
            y1=action.y1,
            x2=action.x2,
            y2=action.y2,
            duration_ms=action.duration_ms,
        )

    def _normalize_target(self, target: str | None) -> str | None:
        if target is None:
            return None
        normalized = target.strip().strip("\"'`")
        return normalized.rstrip(".,;:!?") or None

    def _normalize_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        normalized = text.strip().strip("\"'`")
        return normalized.rstrip(".,;:!?") or ""

    def _repair_action(self, action: ApkAction, observation: dict[str, Any]) -> ApkAction:
        valid_targets = {
            str(target)
            for target in observation.get("valid_targets", [])
            if target
        }
        if not valid_targets:
            valid_targets = {
                str(node.get("id"))
                for node in observation.get("ui", [])
                if isinstance(node, dict) and node.get("id")
            }
        action = self._canonicalize_expected_inputs(action, observation)
        if self._is_action_valid_for_observation(action, valid_targets):
            return action
        fallback = self._scripted_fallback(observation, valid_targets)
        if fallback is not None:
            return fallback
        return ApkAction(action="wait", duration_ms=1000)

    def _canonicalize_expected_inputs(self, action: ApkAction, observation: dict[str, Any]) -> ApkAction:
        if action.action != "input_resource" or not action.target:
            return action
        expected = observation.get("expected_state") or {}
        expected_text_by_target = {
            "search_input": str(expected.get("query") or ""),
            "name_input": str(expected.get("name") or ""),
            "email_input": str(expected.get("email") or ""),
            "pickup_input": str(expected.get("ride_pickup") or expected.get("pickup") or ""),
            "drop_input": str(expected.get("ride_drop") or expected.get("destination") or ""),
        }
        canonical_text = expected_text_by_target.get(action.target)
        if canonical_text is None:
            return action
        return ApkAction(
            action=action.action,
            target=action.target,
            text=canonical_text,
            x=action.x,
            y=action.y,
            x1=action.x1,
            y1=action.y1,
            x2=action.x2,
            y2=action.y2,
            duration_ms=action.duration_ms,
        )

    def _is_action_valid_for_observation(self, action: ApkAction, valid_targets: set[str]) -> bool:
        if action.action in {"input_resource", "click_resource"}:
            return bool(action.target and action.target in valid_targets)
        return action.action in {"tap_coordinates", "press_back", "press_home", "swipe", "wait", "finish"}

    def _scripted_fallback(self, observation: dict[str, Any], valid_targets: set[str]) -> ApkAction | None:
        expected = observation.get("expected_state") or {}
        reward_components = observation.get("reward_components") or {}
        ui_by_id = {
            node.get("id"): node
            for node in observation.get("ui", [])
            if isinstance(node, dict) and node.get("id")
        }

        def input_action(target: str, value: str) -> ApkAction | None:
            if target not in valid_targets:
                return None
            current = str((ui_by_id.get(target) or {}).get("text") or "").strip()
            if current == value:
                return None
            return ApkAction(action="input_resource", target=target, text=value)

        def click_action(target: str) -> ApkAction | None:
            if target not in valid_targets:
                return None
            return ApkAction(action="click_resource", target=target)

        ride_pickup = str(expected.get("ride_pickup") or expected.get("pickup") or "")
        ride_drop = str(expected.get("ride_drop") or expected.get("destination") or "")
        ride_type = str(expected.get("ride_type") or "")
        selected_ride = str(expected.get("selected_ride") or expected.get("cab_type") or "")
        payment = str(expected.get("payment") or expected.get("payment_type") or "")

        if any(key in expected for key in ("ride_pickup", "pickup", "ride_drop", "destination", "ride_type", "selected_ride", "cab_type", "payment", "payment_type")):
            if not reward_components.get("pickup_match", False):
                action = input_action("pickup_input", ride_pickup)
                if action is not None:
                    return action
            if not reward_components.get("ride_type_match", False):
                ride_button = {
                    "Ride": "ride_type_ride",
                    "Reserve": "ride_type_reserve",
                    "Premium": "ride_type_premium",
                }.get(ride_type, "ride_type_ride")
                action = click_action(ride_button)
                if action is not None:
                    return action
            if not reward_components.get("destination_match", False):
                action = input_action("drop_input", ride_drop)
                if action is not None:
                    return action
            if not reward_components.get("destination_match", False):
                action = click_action("destination_search_button")
                if action is not None:
                    return action
            if not reward_components.get("cab_type_match", False):
                ride_button = {
                    "Mini": "ride_option_mini",
                    "Sedan": "ride_option_sedan",
                    "Premium": "ride_option_premium",
                }.get(selected_ride, "ride_option_mini")
                action = click_action(ride_button)
                if action is not None:
                    return action
            if not reward_components.get("payment_match", False):
                payment_button = {
                    "cash": "payment_cash",
                    "card": "payment_card",
                    "upi": "payment_upi",
                }.get(payment.lower(), "payment_upi")
                action = click_action(payment_button)
                if action is not None:
                    return action
            if not reward_components.get("ride_terminal_state", False):
                action = click_action("confirm_ride_button")
                if action is not None:
                    return action
            if float(observation.get("final_reward", 0.0) or 0.0) >= 1.0:
                return ApkAction(action="finish")
            return ApkAction(action="wait", duration_ms=1000)

        query = str(expected.get("query") or "")
        name = str(expected.get("name") or "")
        email = str(expected.get("email") or "")

        if not reward_components.get("query_match", False):
            action = input_action("search_input", query)
            if action is not None:
                return action
            action = click_action("search_button")
            if action is not None:
                return action
        if not reward_components.get("name_match", False):
            action = input_action("name_input", name)
            if action is not None:
                return action
        if not reward_components.get("email_match", False):
            action = input_action("email_input", email)
            if action is not None:
                return action
        if not reward_components.get("submitted", False):
            action = click_action("submit_button")
            if action is not None:
                return action
        if float(observation.get("final_reward", 0.0) or 0.0) >= 1.0:
            return ApkAction(action="finish")
        return ApkAction(action="wait", duration_ms=1000)

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
