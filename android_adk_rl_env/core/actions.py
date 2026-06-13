"""Strict high-level mobile action schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

MobileActionType = Literal[
    "tap_element",
    "tap_coordinates",
    "type_text",
    "press_back",
    "press_home",
    "swipe",
    "wait",
    "finish",
]

VALID_ACTION_TYPES: tuple[str, ...] = (
    "tap_element",
    "tap_coordinates",
    "type_text",
    "press_back",
    "press_home",
    "swipe",
    "wait",
    "finish",
)


class ActionValidationError(ValueError):
    """Raised when a model action does not match the mobile action schema."""

    def __init__(self, reason: str, valid_actions: tuple[str, ...] = VALID_ACTION_TYPES) -> None:
        super().__init__(reason)
        self.reason = reason
        self.valid_actions = valid_actions


@dataclass(frozen=True)
class MobileAction:
    """Canonical action format used at the task/harness boundary."""

    type: MobileActionType
    element_id: str | None = None
    x: int | None = None
    y: int | None = None
    text: str | None = None
    x1: int | None = None
    y1: int | None = None
    x2: int | None = None
    y2: int | None = None
    duration_ms: int | None = None

    @classmethod
    def parse_json(cls, raw: str | dict[str, Any]) -> "MobileAction":
        if isinstance(raw, str):
            try:
                payload = json.loads(strip_code_fence(raw))
            except json.JSONDecodeError as exc:
                raise ActionValidationError("invalid_json_action") from exc
        else:
            payload = raw
        if not isinstance(payload, dict):
            raise ActionValidationError("invalid_action_schema")
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MobileAction":
        action_type = payload.get("type", payload.get("action"))
        action_type = _legacy_type(action_type)
        if action_type not in VALID_ACTION_TYPES:
            raise ActionValidationError("unknown_action_type")

        action = cls(
            type=action_type,  # type: ignore[arg-type]
            element_id=_optional_str(payload.get("element_id", payload.get("target"))),
            x=_optional_int(payload.get("x")),
            y=_optional_int(payload.get("y")),
            text=_optional_str(payload.get("text")),
            x1=_optional_int(payload.get("x1")),
            y1=_optional_int(payload.get("y1")),
            x2=_optional_int(payload.get("x2")),
            y2=_optional_int(payload.get("y2")),
            duration_ms=_optional_int(payload.get("duration_ms")),
        )
        action.validate()
        return action

    def validate(self) -> None:
        if self.type == "tap_element" and not self.element_id:
            raise ActionValidationError("tap_missing_element_id")
        if self.type == "tap_coordinates" and (self.x is None or self.y is None):
            raise ActionValidationError("tap_missing_coordinates")
        if self.type == "type_text":
            if not self.element_id:
                raise ActionValidationError("type_missing_element_id")
            if self.text is None:
                raise ActionValidationError("type_without_text")
        if self.type == "swipe" and any(
            value is None for value in (self.x1, self.y1, self.x2, self.y2)
        ):
            raise ActionValidationError("swipe_missing_coordinates")
        if self.type in {"press_back", "press_home", "wait", "finish"} and self.element_id is not None:
            raise ActionValidationError(f"{self.type}_does_not_use_element_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "element_id": self.element_id,
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "duration_ms": self.duration_ms,
        }


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _legacy_type(raw: Any) -> Any:
    mapping = {
        "click_resource": "tap_element",
        "input_resource": "type_text",
        "press_back": "press_back",
        "wait": "wait",
        "finish": "finish",
    }
    return mapping.get(raw, raw)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ActionValidationError("invalid_action_schema")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ActionValidationError("invalid_action_schema")
    return value
