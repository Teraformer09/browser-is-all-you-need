"""Scripted APK policy used for smoke tests and demonstration data."""

from __future__ import annotations

from android_adk_rl_env.apk_env import ApkAction
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


class ScriptedApkPolicy:
    def __init__(self, task: DummyApkFormSearchTask | None = None) -> None:
        self.task = task or DummyApkFormSearchTask()
        self.reset()

    def reset(self) -> None:
        self._index = 0
        self._actions = [
            ApkAction("input_resource", target="search_input", text=self.task.query),
            ApkAction("click_resource", target="search_button"),
            ApkAction("input_resource", target="name_input", text=self.task.name),
            ApkAction("input_resource", target="email_input", text=self.task.email),
            ApkAction("press_back"),
            ApkAction("click_resource", target="submit_button"),
            ApkAction("finish"),
        ]

    def act(self, observation: dict[str, object]) -> ApkAction:
        del observation
        if self._index >= len(self._actions):
            return ApkAction("finish")
        action = self._actions[self._index]
        self._index += 1
        return action
