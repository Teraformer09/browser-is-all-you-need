"""Step-based APK environment for model-driven Android RL rollouts."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.env import StepResult
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask

ApkActionName = Literal["click_resource", "input_resource", "press_back", "wait", "finish"]


@dataclass(frozen=True)
class ApkAction:
    """Structured Android action emitted by a policy."""

    action: ApkActionName
    target: str | None = None
    text: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ApkAction":
        return cls(
            action=raw.get("action"),
            target=raw.get("target"),
            text=raw.get("text"),
        )

    def to_dict(self) -> dict[str, str | None]:
        return {"action": self.action, "target": self.target, "text": self.text}


class DummyApkEnv:
    """One-step-at-a-time environment around the real dummy APK."""

    def __init__(
        self,
        task: DummyApkFormSearchTask | None = None,
        device: AdbDevice | None = None,
        max_steps: int | None = None,
        shaped_rewards: bool = True,
    ) -> None:
        self.task = task or DummyApkFormSearchTask()
        self.device = device or AdbDevice(package=self.task.package)
        self.max_steps = max_steps or self.task.max_steps
        self.shaped_rewards = shaped_rewards
        self.steps = 0
        self.done = False
        self.last_error: str | None = None
        self.last_action: dict[str, str | None] | None = None

    def reset(self) -> dict[str, Any]:
        self.device.wait_for_device()
        self.device.clear_app_data()
        self.device.launch_app()
        self.steps = 0
        self.done = False
        self.last_error = None
        self.last_action = None
        return self.observe()

    def step(self, raw_action: ApkAction | dict[str, Any]) -> StepResult:
        if self.done:
            observation = self.observe()
            return StepResult(
                observation=observation,
                reward=observation["reward"],
                done=True,
                info={"error": "environment already done"},
            )

        action = raw_action if isinstance(raw_action, ApkAction) else ApkAction.from_dict(raw_action)
        self.steps += 1
        self.last_action = action.to_dict()
        self.last_error = self._validate(action)

        if self.last_error is None:
            try:
                self._execute(action)
            except Exception as exc:  # noqa: BLE001 - surface ADB/UI failures in info.
                self.last_error = f"{type(exc).__name__}: {exc}"

        observation = self.observe()
        final_reward = observation["final_reward"]
        reward = observation["reward"]
        self.done = (
            final_reward >= 1.0
            or self.steps >= self.max_steps
            or action.action == "finish"
        )
        observation["done"] = self.done

        return StepResult(
            observation=observation,
            reward=reward,
            done=self.done,
            info={
                "steps": self.steps,
                "action": action.to_dict(),
                "error": self.last_error,
                "final_reward": final_reward,
                "invalid_action": self.last_error is not None,
            },
        )

    def observe(self) -> dict[str, Any]:
        prefs_xml = self._safe_read_prefs()
        ui_nodes, ui_error = self._safe_dump_ui()
        components = self.task.reward_components_from_prefs(prefs_xml)
        final_reward = self.task.reward_from_prefs(prefs_xml)
        shaped_reward = self.task.shaped_reward_from_prefs(prefs_xml)

        return {
            "task": self.task.name_label,
            "goal": self.task.goal,
            "package": self.task.package,
            "steps": self.steps,
            "max_steps": self.max_steps,
            "done": self.done,
            "ui": ui_nodes,
            "ui_error": ui_error,
            "last_action": self.last_action,
            "last_error": self.last_error,
            "expected_state": self.task.expected_state(),
            "reward_components": components,
            "reward": shaped_reward if self.shaped_rewards else final_reward,
            "final_reward": final_reward,
            "shared_prefs_present": bool(prefs_xml.strip()),
        }

    def _validate(self, action: ApkAction) -> str | None:
        if action.action not in {"click_resource", "input_resource", "press_back", "wait", "finish"}:
            return f"unsupported action: {action.action}"
        if action.action in {"click_resource", "input_resource"}:
            if action.target not in self.task.resource_names:
                return f"unsupported target for {action.action}: {action.target}"
        if action.action == "input_resource" and action.text is None:
            return "input_resource requires text"
        if action.action in {"press_back", "wait", "finish"} and action.target is not None:
            return f"{action.action} does not use target"
        return None

    def _execute(self, action: ApkAction) -> None:
        if action.action == "click_resource":
            assert action.target is not None
            self.device.click_resource(action.target)
        elif action.action == "input_resource":
            assert action.target is not None
            self.device.input_resource(action.target, action.text or "")
        elif action.action == "press_back":
            self.device.press_back()
        elif action.action == "wait":
            time.sleep(0.5)
        elif action.action == "finish":
            return

    def _safe_read_prefs(self) -> str:
        try:
            return self.device.read_shared_prefs()
        except Exception:
            return ""

    def _safe_dump_ui(self) -> tuple[list[dict[str, object]], str | None]:
        try:
            return self.device.dump_resource_nodes(self.task.resource_names), None
        except Exception as exc:  # noqa: BLE001 - observations should survive UI dump errors.
            return [], f"{type(exc).__name__}: {exc}"
