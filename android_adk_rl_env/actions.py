"""Action schema for the local Android ADK-style environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ActionName = Literal[
    "open_app",
    "tap",
    "input_text",
    "submit",
    "navigate_back",
]


@dataclass(frozen=True)
class Action:
    """A simple Android-style tool call."""

    name: ActionName
    target: str | None = None
    text: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "target": self.target,
            "text": self.text,
        }
