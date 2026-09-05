"""Environment loop and mock Android device implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uber_clone_031.harness.backend.actions import Action
from uber_clone_031.harness.backend.tasks.base import Task


@dataclass
class StepResult:
    """Result returned after each agent action."""

    observation: dict[str, Any]
    reward: float
    done: bool
    info: dict[str, Any] = field(default_factory=dict)


class MockAndroidDevice:
    """Deterministic Android notes-app simulator.

    This class is the only Android boundary in the runnable scaffold. It can be
    replaced with an ADB, UIAutomator, Appium, or AndroidWorld controller later.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.current_app: str | None = None
        self.screen = "launcher"
        self.notes: list[dict[str, str]] = []
        self.draft: dict[str, str] = {}
        self.focus: str | None = None
        self.last_error: str | None = None

    def apply(self, action: Action) -> None:
        self.last_error = None
        handlers = {
            "open_app": self._open_app,
            "tap": self._tap,
            "input_text": self._input_text,
            "submit": self._submit,
            "navigate_back": self._navigate_back,
        }
        handlers[action.name](action)

    def observe(self) -> dict[str, Any]:
        return {
            "current_app": self.current_app,
            "screen": self.screen,
            "focus": self.focus,
            "draft": dict(self.draft),
            "notes": [dict(note) for note in self.notes],
            "last_error": self.last_error,
        }

    def has_note(self, title: str, body: str) -> bool:
        return any(
            note.get("title") == title and note.get("body") == body
            for note in self.notes
        )

    def _open_app(self, action: Action) -> None:
        if action.target != "notes":
            self.last_error = f"unknown app: {action.target}"
            return
        self.current_app = "notes"
        self.screen = "notes_list"
        self.focus = None

    def _tap(self, action: Action) -> None:
        if self.current_app != "notes":
            self.last_error = "no app open"
            return
        if action.target == "new_note" and self.screen == "notes_list":
            self.screen = "note_editor"
            self.draft = {"title": "", "body": ""}
            self.focus = "title"
            return
        if action.target in {"title", "body"} and self.screen == "note_editor":
            self.focus = action.target
            return
        self.last_error = f"cannot tap {action.target} on {self.screen}"

    def _input_text(self, action: Action) -> None:
        if self.screen != "note_editor" or self.focus not in {"title", "body"}:
            self.last_error = "no editable field focused"
            return
        self.draft[self.focus] = action.text or ""

    def _submit(self, action: Action) -> None:
        del action
        if self.screen != "note_editor":
            self.last_error = "nothing to submit"
            return
        title = self.draft.get("title", "").strip()
        body = self.draft.get("body", "").strip()
        if not title or not body:
            self.last_error = "title and body are required"
            return
        self.notes.append({"title": title, "body": body})
        self.draft = {}
        self.focus = None
        self.screen = "notes_list"

    def _navigate_back(self, action: Action) -> None:
        del action
        if self.screen == "note_editor":
            self.screen = "notes_list"
            self.draft = {}
            self.focus = None
            return
        self.screen = "launcher"
        self.current_app = None
        self.focus = None


class AndroidAdkEnv:
    """Small RL/evaluation loop for Android-style tasks."""

    def __init__(self, task: Task, device: MockAndroidDevice | None = None) -> None:
        self.task = task
        self.device = device or MockAndroidDevice()
        self.steps = 0
        self.done = False

    def reset(self) -> dict[str, Any]:
        self.device.reset()
        self.steps = 0
        self.done = False
        self.task.initialize(self.device)
        return self._observation()

    def step(self, action: Action) -> StepResult:
        if self.done:
            return StepResult(
                observation=self._observation(),
                reward=self.task.reward(self.device),
                done=True,
                info={"error": "environment already done"},
            )

        self.device.apply(action)
        self.steps += 1

        reward = self.task.reward(self.device)
        self.done = reward >= 1.0 or self.steps >= self.task.max_steps

        return StepResult(
            observation=self._observation(),
            reward=reward,
            done=self.done,
            info={"steps": self.steps, "action": action.to_dict()},
        )

    def _observation(self) -> dict[str, Any]:
        observation = self.device.observe()
        observation["goal"] = self.task.goal
        observation["max_steps"] = self.task.max_steps
        observation["steps"] = self.steps
        return observation
