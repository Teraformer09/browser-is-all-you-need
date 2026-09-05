"""Base task protocol."""

from __future__ import annotations

from typing import Protocol


class Device(Protocol):
    def has_note(self, title: str, body: str) -> bool:
        """Return whether a durable note exists."""


class Task(Protocol):
    name: str
    goal: str
    max_steps: int

    def initialize(self, device: Device) -> None:
        """Prepare device/app state before a rollout."""

    def reward(self, device: Device) -> float:
        """Return the current task reward."""
