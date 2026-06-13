"""Conservative safety policy for mobile app actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SafetyDecision:
    block: bool
    reason: str | None = None


class SafetyPolicy:
    """Blocks obviously destructive real-app actions when safe mode is enabled."""

    blocked_terms = (
        "pay",
        "purchase",
        "send",
        "delete",
        "remove account",
        "share contacts",
        "confirm payment",
        "book real",
    )

    def __init__(self, safe_mode: bool = True) -> None:
        self.safe_mode = safe_mode

    def validate_action(self, action: Any, observation: dict[str, Any], task: Any) -> SafetyDecision:
        if not self.safe_mode:
            return SafetyDecision(block=False)
        if str(getattr(task, "package", "")) == "com.primeintellect.dummyrl":
            return SafetyDecision(block=False)
        action_text = str(getattr(action, "text", "") or "").lower()
        action_target = str(getattr(action, "target", getattr(action, "element_id", "")) or "").lower()
        screen_text = " ".join(str(elem.get("text", "")) for elem in observation.get("ui", []) if isinstance(elem, dict)).lower()
        haystack = " ".join([action_text, action_target, screen_text])
        if any(term in haystack for term in self.blocked_terms):
            return SafetyDecision(block=True, reason="destructive_action")
        return SafetyDecision(block=False)
