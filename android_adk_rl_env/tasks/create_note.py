"""One runnable AndroidWorld-style task."""

from __future__ import annotations

from dataclasses import dataclass

from android_adk_rl_env.tasks.base import Device


@dataclass(frozen=True)
class CreateNoteTask:
    """Create a specific note in the mock Android notes app."""

    title: str = "AndroidWorld Pilot"
    body: str = "Validate one runnable task."
    max_steps: int = 8
    name: str = "CreateNoteTask"

    @property
    def goal(self) -> str:
        return (
            "Open the Notes app and create a note titled "
            f"'{self.title}' with body '{self.body}'."
        )

    def initialize(self, device: Device) -> None:
        del device

    def reward(self, device: Device) -> float:
        return 1.0 if device.has_note(self.title, self.body) else 0.0
