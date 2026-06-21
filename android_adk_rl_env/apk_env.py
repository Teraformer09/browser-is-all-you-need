"""Step-based APK environment for model-driven Android RL rollouts."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.core.actions import ActionValidationError, MobileAction
from android_adk_rl_env.core.observations import ObservationMode, build_observation
from android_adk_rl_env.core.safety import SafetyPolicy
from android_adk_rl_env.env import StepResult
from android_adk_rl_env.reset_manager import reset_task_device
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask

ApkActionName = Literal[
    "click_resource",
    "input_resource",
    "tap_coordinates",
    "press_back",
    "press_home",
    "swipe",
    "wait",
    "finish",
]


@dataclass(frozen=True)
class ApkAction:
    """Structured Android action emitted by a policy."""

    action: ApkActionName
    target: str | None = None
    text: str | None = None
    x: int | None = None
    y: int | None = None
    x1: int | None = None
    y1: int | None = None
    x2: int | None = None
    y2: int | None = None
    duration_ms: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ApkAction":
        if "type" in raw:
            return cls.from_mobile_action(MobileAction.from_dict(raw))
        return cls(
            action=raw.get("action"),
            target=raw.get("target"),
            text=raw.get("text"),
            x=raw.get("x"),
            y=raw.get("y"),
            x1=raw.get("x1"),
            y1=raw.get("y1"),
            x2=raw.get("x2"),
            y2=raw.get("y2"),
            duration_ms=raw.get("duration_ms"),
        )

    @classmethod
    def from_mobile_action(cls, action: MobileAction) -> "ApkAction":
        mapping = {
            "tap_element": "click_resource",
            "type_text": "input_resource",
            "tap_coordinates": "tap_coordinates",
            "press_back": "press_back",
            "press_home": "press_home",
            "swipe": "swipe",
            "wait": "wait",
            "finish": "finish",
        }
        return cls(
            action=mapping[action.type],  # type: ignore[arg-type]
            target=action.element_id,
            text=action.text,
            x=action.x,
            y=action.y,
            x1=action.x1,
            y1=action.y1,
            x2=action.x2,
            y2=action.y2,
            duration_ms=action.duration_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "duration_ms": self.duration_ms,
        }

    def to_mobile_dict(self) -> dict[str, Any]:
        mapping = {
            "click_resource": "tap_element",
            "input_resource": "type_text",
            "tap_coordinates": "tap_coordinates",
            "press_back": "press_back",
            "press_home": "press_home",
            "swipe": "swipe",
            "wait": "wait",
            "finish": "finish",
        }
        return {
            "type": mapping.get(self.action, self.action),
            "element_id": self.target,
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "duration_ms": self.duration_ms,
        }


class DummyApkEnv:
    """One-step-at-a-time environment around the real dummy APK."""

    def __init__(
        self,
        task: DummyApkFormSearchTask | None = None,
        device: AdbDevice | None = None,
        max_steps: int | None = None,
        shaped_rewards: bool = True,
        observation_mode: ObservationMode = "full_ui_tree",
        safe_mode: bool = True,
        invalid_action_penalty: float = -0.05,
    ) -> None:
        self.task = task or DummyApkFormSearchTask()
        self.device = device or AdbDevice(package=self.task.package)
        self.max_steps = max_steps or self.task.max_steps
        self.shaped_rewards = shaped_rewards
        self.observation_mode = observation_mode
        self.safety = SafetyPolicy(safe_mode=safe_mode)
        self.invalid_action_penalty = invalid_action_penalty
        self.steps = 0
        self.done = False
        self.last_error: str | None = None
        self.last_action: dict[str, Any] | None = None
        self.reset_failed = False
        self.invalid_action_seen = False
        self.forbidden_action_seen = False
        self.finish_after_success = True
        self.ui_tree_xml: str | None = None
        self.last_reset_metadata: dict[str, Any] | None = None

    def reset(self) -> dict[str, Any]:
        self.task = self.task.new_episode()
        self.steps = 0
        self.done = False
        self.last_error = None
        self.last_action = None
        self.reset_failed = False
        self.invalid_action_seen = False
        self.forbidden_action_seen = False
        self.finish_after_success = True
        self.ui_tree_xml = None
        self.last_reset_metadata = None
        try:
            self.task.initialize_task(self.device)
            self.last_reset_metadata = reset_task_device(self.task, self.device).to_dict()
            self.task.reset_episode(self.device)
        except Exception as exc:  # noqa: BLE001
            self.done = True
            self.reset_failed = True
            self.last_error = "device_reset_failed"
            observation = self.observe()
            observation["reset_error"] = f"{type(exc).__name__}: {exc}"
            return observation
        return self.observe()

    def step(self, raw_action: ApkAction | dict[str, Any] | str) -> StepResult:
        if self.done:
            observation = self.observe()
            return StepResult(
                observation=observation,
                reward=observation["reward"],
                done=True,
                info={"error": "environment already done"},
            )

        try:
            action = self._coerce_action(raw_action)
        except ActionValidationError as exc:
            self.steps += 1
            self.last_error = exc.reason
            self.invalid_action_seen = True
            if exc.reason.startswith("finish"):
                self.finish_after_success = False
            self.last_action = raw_action if isinstance(raw_action, dict) else {"raw": str(raw_action)}
            observation = self.observe()
            info = self._info(error="invalid_action_schema", action_valid=False)
            info["schema_error"] = exc.reason
            info["valid_actions"] = list(exc.valid_actions)
            return StepResult(
                observation=observation,
                reward=self.invalid_action_penalty,
                done=False,
                info=info,
            )

        action = self._normalize_action(action)
        self.steps += 1
        self.last_action = action.to_dict()
        self.last_error = self._validate(action)

        if self.last_error is None:
            safety = self.safety.validate_action(action, self.observe(), self.task)
            if safety.block:
                self.last_error = safety.reason or "blocked_by_safety_policy"
                self.forbidden_action_seen = True
            else:
                try:
                    self._execute(action)
                except Exception as exc:  # noqa: BLE001 - surface ADB/UI failures in info.
                    self.last_error = f"{type(exc).__name__}: {exc}"
        else:
            self.invalid_action_seen = True
            if action.action == "finish":
                self.finish_after_success = False

        observation = self.observe()
        final_reward = observation["final_reward"]
        reward = self.invalid_action_penalty if self.last_error is not None else observation["reward"]
        self.done = final_reward >= 1.0 or self.steps >= self.max_steps or action.action == "finish"
        observation["done"] = self.done

        return StepResult(
            observation=observation,
            reward=reward,
            done=self.done,
            info=self._info(error=self.last_error, action_valid=self.last_error is None),
        )

    def observe(self) -> dict[str, Any]:
        prefs_xml = self._safe_read_prefs()
        ui_nodes, ui_error, ui_tree_xml = self._safe_dump_ui()
        apk_state = self.task.state_from_prefs(prefs_xml)
        components = self.task.reward_components_from_prefs(
            prefs_xml,
            no_forbidden_action=not self.forbidden_action_seen,
            no_invalid_action=not self.invalid_action_seen,
            finish_after_success=self.finish_after_success,
        )
        final_reward = self.task.reward_from_prefs(
            prefs_xml,
            no_forbidden_action=not self.forbidden_action_seen,
            no_invalid_action=not self.invalid_action_seen,
            finish_after_success=self.finish_after_success,
        )
        shaped_reward = self.task.shaped_reward_from_prefs(
            prefs_xml,
            no_forbidden_action=not self.forbidden_action_seen,
            no_invalid_action=not self.invalid_action_seen,
            finish_after_success=self.finish_after_success,
        )
        reward = -1.0 if self.reset_failed else (shaped_reward if self.shaped_rewards else final_reward)
        raw = {
            "task": self.task.name_label,
            "task_id": self.task.task_id,
            "episode_id": self.task.episode_id,
            "goal": self.task.goal,
            "package": self.task.package,
            "surface": self.task.surface,
            "difficulty": self.task.difficulty,
            "seed": self.task.seed,
            "backend": getattr(self.device, "name", "adb"),
            "steps": self.steps,
            "step": self.steps,
            "max_steps": self.max_steps,
            "done": self.done,
            "ui": ui_nodes,
            "ui_error": ui_error,
            "ui_tree_xml": ui_tree_xml,
            "last_action": self.last_action,
            "last_error": self.last_error,
            "expected_state": self.task.expected_state(),
            "apk_state": apk_state,
            "reward_components": components,
            "reward": reward,
            "final_reward": final_reward,
            "exact_success": self.task.verify_success({"exact_success": final_reward >= 1.0, "reward_components": components}),
            "screen": apk_state.get("screen") or self._infer_screen(ui_nodes),
            "shared_prefs_present": bool(prefs_xml.strip()),
            "reset_metadata": self.last_reset_metadata,
        }
        raw.update(build_observation(raw, mode=self.observation_mode))
        return raw

    def _coerce_action(self, raw_action: ApkAction | dict[str, Any] | str) -> ApkAction:
        if isinstance(raw_action, ApkAction):
            return raw_action
        if isinstance(raw_action, str):
            return ApkAction.from_mobile_action(MobileAction.parse_json(raw_action))
        if "type" in raw_action:
            return ApkAction.from_mobile_action(MobileAction.from_dict(raw_action))
        action = ApkAction.from_dict(raw_action)
        MobileAction.from_dict(action.to_mobile_dict())
        return action

    def _normalize_action(self, action: ApkAction) -> ApkAction:
        if action.target is None:
            return action
        target = action.target.rsplit("/", 1)[-1]
        return ApkAction(
            action=action.action,
            target=target,
            text=action.text,
            x=action.x,
            y=action.y,
            x1=action.x1,
            y1=action.y1,
            x2=action.x2,
            y2=action.y2,
            duration_ms=action.duration_ms,
        )

    def _validate(self, action: ApkAction) -> str | None:
        if action.action not in {
            "click_resource",
            "input_resource",
            "tap_coordinates",
            "press_back",
            "press_home",
            "swipe",
            "wait",
            "finish",
        }:
            return f"unsupported action: {action.action}"
        if action.action in {"click_resource", "input_resource"}:
            if action.target not in self.task.resource_names:
                return "tap_unknown_element_id" if action.action == "click_resource" else f"unsupported target for {action.action}: {action.target}"
        if action.action == "input_resource" and action.text is None:
            return "input_resource requires text"
        if action.action == "tap_coordinates" and (action.x is None or action.y is None):
            return "tap_missing_coordinates"
        if action.action == "swipe" and any(value is None for value in (action.x1, action.y1, action.x2, action.y2)):
            return "swipe_missing_coordinates"
        if action.action in {"press_back", "press_home", "wait", "finish"} and action.target is not None:
            return f"{action.action} does not use target"
        if action.action == "finish" and self.observe().get("final_reward", 0.0) < 1.0:
            return "finish is only valid after final_reward is 1.0"
        return None

    def _execute(self, action: ApkAction) -> None:
        if action.action == "click_resource":
            assert action.target is not None
            self.device.click_resource(action.target)
        elif action.action == "input_resource":
            assert action.target is not None
            self.device.input_resource(action.target, action.text or "")
        elif action.action == "tap_coordinates":
            assert action.x is not None and action.y is not None
            self.device.tap_coordinates(action.x, action.y)
        elif action.action == "press_back":
            self.device.press_back()
        elif action.action == "press_home":
            self.device.press_home()
        elif action.action == "swipe":
            assert action.x1 is not None and action.y1 is not None and action.x2 is not None and action.y2 is not None
            self.device.swipe(action.x1, action.y1, action.x2, action.y2, action.duration_ms or 300)
        elif action.action == "wait":
            time.sleep(0.5)
        elif action.action == "finish":
            return

    def _safe_read_prefs(self) -> str:
        try:
            return self.device.read_shared_prefs()
        except Exception:
            return ""

    def _safe_dump_ui(self) -> tuple[list[dict[str, object]], str | None, str | None]:
        try:
            xml_text = self.device.dump_ui() if hasattr(self.device, "dump_ui") else None
            self.ui_tree_xml = xml_text
            if xml_text is not None and hasattr(self.device, "_resource_nodes_from_xml"):
                nodes = self.device._resource_nodes_from_xml(xml_text, self.task.resource_names)
            else:
                nodes = self.device.dump_resource_nodes(self.task.resource_names)
            return nodes, None, xml_text
        except Exception as exc:  # noqa: BLE001 - observations should survive UI dump errors.
            return [], f"{type(exc).__name__}: {exc}", self.ui_tree_xml

    def _infer_screen(self, ui_nodes: list[dict[str, object]]) -> str:
        text = " ".join(str(node.get("text", "")) for node in ui_nodes).lower()
        if "submitted:" in text:
            return "submitted"
        if "missing fields" in text:
            return "validation_error"
        return "form"

    def _info(self, error: str | None, action_valid: bool) -> dict[str, Any]:
        observation = self.observe()
        return {
            "task_id": self.task.task_id,
            "episode_id": self.task.episode_id,
            "step": self.steps,
            "backend": observation.get("backend", "adb"),
            "action_valid": action_valid,
            "reward_components": observation.get("reward_components", {}),
            "exact_success": observation.get("exact_success", False),
            "apk_state": observation.get("apk_state", {}),
            "error": error,
            "final_reward": observation.get("final_reward", 0.0),
            "invalid_action": not action_valid,
            "trajectory_quality": "success" if observation.get("exact_success") else "partial" if observation.get("reward", 0.0) > 0 else "failure",
        }
