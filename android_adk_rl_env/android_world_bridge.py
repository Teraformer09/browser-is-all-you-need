"""Optional AndroidWorld integration for the dummy APK RL task.

This module intentionally keeps AndroidWorld imports optional. The rest of the
repo remains runnable with plain ADB when AndroidWorld is not installed.
"""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import ApkAction
from android_adk_rl_env.core.observations import build_observation
from android_adk_rl_env.env import StepResult
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


class AndroidWorldNotInstalledError(RuntimeError):
    """Raised when native AndroidWorld integration is requested but missing."""


@dataclass(frozen=True)
class AndroidWorldStatus:
    installed: bool
    reason: str | None = None


def android_world_status() -> AndroidWorldStatus:
    try:
        importlib.import_module("android_world")
    except Exception as exc:  # noqa: BLE001 - import can fail from optional deps too.
        return AndroidWorldStatus(False, f"{type(exc).__name__}: {exc}")
    return AndroidWorldStatus(True)


def require_android_world() -> None:
    status = android_world_status()
    if not status.installed:
        raise AndroidWorldNotInstalledError(
            "AndroidWorld is not installed. Install google-research/android_world "
            "and launch its emulator with the required -grpc port before using "
            "--backend android_world. Import error: " + (status.reason or "unknown")
        )


class AndroidWorldDummyApkEnv:
    """Step env that uses AndroidWorld for observation/action execution.

    Reward is still read from the dummy APK's durable SharedPreferences. This
    keeps evaluation equivalent to the ADB-only env while using AndroidWorld's
    AsyncEnv/JSONAction stack for the Android interaction layer.
    """

    def __init__(
        self,
        android_env: Any,
        task: DummyApkFormSearchTask | None = None,
        adb_device: AdbDevice | None = None,
        max_steps: int | None = None,
        shaped_rewards: bool = True,
        wait_to_stabilize: bool = False,
    ) -> None:
        self.android_env = android_env
        self.task = task or DummyApkFormSearchTask()
        self.adb_device = adb_device or AdbDevice(package=self.task.package)
        self.max_steps = max_steps or self.task.max_steps
        self.shaped_rewards = shaped_rewards
        self.wait_to_stabilize = wait_to_stabilize
        self.steps = 0
        self.done = False
        self.last_error: str | None = None
        self.last_action: dict[str, str | None] | None = None

    def reset(self) -> dict[str, Any]:
        self.task = self.task.new_episode()
        if hasattr(self.adb_device, "reset_app"):
            self.adb_device.reset_app(episode_id=self.task.episode_id)
        else:
            self.adb_device.wait_for_device()
            self.adb_device.clear_app_data()
            try:
                self.adb_device.launch_app(episode_id=self.task.episode_id)
            except TypeError:
                if hasattr(self.adb_device, "episode_id"):
                    self.adb_device.episode_id = self.task.episode_id
                self.adb_device.launch_app()
        self.steps = 0
        self.done = False
        self.last_error = None
        self.last_action = None
        # Refresh AndroidWorld state after app launch. Keep this permissive so
        # test doubles can use a simpler reset signature.
        try:
            self.android_env.reset(go_home=False)
        except TypeError:
            self.android_env.reset()
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"android_world_reset_failed: {type(exc).__name__}: {exc}"
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
        action = self._normalize_action(action)
        self.steps += 1
        self.last_action = action.to_dict()
        self.last_error = self._validate(action)

        if self.last_error is None:
            try:
                self._execute(action)
            except Exception as exc:  # noqa: BLE001 - expose AndroidWorld failures.
                self.last_error = f"{type(exc).__name__}: {exc}"

        observation = self.observe()
        final_reward = observation["final_reward"]
        reward = observation["reward"]
        self.done = final_reward >= 1.0 or self.steps >= self.max_steps
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
                "backend": "android_world",
            },
        )

    def observe(self) -> dict[str, Any]:
        prefs_xml = self._safe_read_prefs()
        ui_nodes, ui_error = self._safe_get_ui_nodes()
        apk_state = self.task.state_from_prefs(prefs_xml)
        components = self.task.reward_components_from_prefs(prefs_xml)
        final_reward = self.task.reward_from_prefs(prefs_xml)
        shaped_reward = self.task.shaped_reward_from_prefs(prefs_xml)
        raw = {
            "task": self.task.name_label,
            "task_id": self.task.task_id,
            "episode_id": self.task.episode_id,
            "goal": self.task.goal,
            "package": self.task.package,
            "backend": "android_world",
            "steps": self.steps,
            "step": self.steps,
            "max_steps": self.max_steps,
            "done": self.done,
            "ui": ui_nodes,
            "ui_error": ui_error,
            "last_action": self.last_action,
            "last_error": self.last_error,
            "expected_state": self.task.expected_state(),
            "apk_state": apk_state,
            "reward_components": components,
            "reward": shaped_reward if self.shaped_rewards else final_reward,
            "final_reward": final_reward,
            "exact_success": final_reward >= 1.0,
            "screen": apk_state.get("screen") or "form",
            "shared_prefs_present": bool(prefs_xml.strip()),
        }
        raw.update(build_observation(raw, mode="compact_text"))
        return raw

    def close(self) -> None:
        close = getattr(self.android_env, "close", None)
        if callable(close):
            close()

    def _normalize_action(self, action: ApkAction) -> ApkAction:
        if action.target is None:
            return action
        return ApkAction(
            action=action.action,
            target=self._local_resource_name(action.target),
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
                return f"unsupported target for {action.action}: {action.target}"
            if self._find_element_index(action.target) is None:
                return f"resource not visible in AndroidWorld state: {action.target}"
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
        json_action = self._json_action_module()
        if action.action == "click_resource":
            index = self._require_element_index(action.target)
            self.android_env.execute_action(json_action.JSONAction(action_type=json_action.CLICK, index=index))
        elif action.action == "input_resource":
            index = self._require_element_index(action.target)
            self.android_env.execute_action(
                json_action.JSONAction(
                    action_type=json_action.INPUT_TEXT,
                    index=index,
                    text=action.text or "",
                    clear_text=True,
                )
            )
        elif action.action == "tap_coordinates":
            self.android_env.execute_action(
                json_action.JSONAction(action_type=json_action.CLICK, x=action.x, y=action.y)
            )
        elif action.action == "press_back":
            self.android_env.execute_action(json_action.JSONAction(action_type=json_action.NAVIGATE_BACK))
        elif action.action == "press_home":
            self.android_env.execute_action(json_action.JSONAction(action_type=json_action.NAVIGATE_HOME))
        elif action.action == "swipe":
            direction = self._swipe_direction(action)
            if hasattr(json_action, "SWIPE"):
                self.android_env.execute_action(json_action.JSONAction(action_type=json_action.SWIPE, direction=direction))
            else:
                self.android_env.execute_action(json_action.JSONAction(action_type=json_action.SCROLL, direction=direction))
        elif action.action == "wait":
            try:
                self.android_env.execute_action(json_action.JSONAction(action_type=json_action.WAIT))
            except Exception:
                time.sleep(0.5)
        elif action.action == "finish":
            self.android_env.execute_action(
                json_action.JSONAction(action_type=json_action.STATUS, goal_status="complete")
            )

    def _require_element_index(self, resource_name: str | None) -> int:
        index = self._find_element_index(resource_name)
        if index is None:
            raise LookupError(f"resource not visible in AndroidWorld state: {resource_name}")
        return index

    def _find_element_index(self, resource_name: str | None) -> int | None:
        if not resource_name:
            return None
        elements = self._get_state_ui_elements()
        full_id = f"{self.task.package}:id/{resource_name}"
        for index, element in enumerate(elements):
            if self._element_matches(element, resource_name, full_id):
                return index
        return None

    def _swipe_direction(self, action: ApkAction) -> str:
        dx = (action.x2 or 0) - (action.x1 or 0)
        dy = (action.y2 or 0) - (action.y1 or 0)
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "down" if dy > 0 else "up"

    def _safe_get_ui_nodes(self) -> tuple[list[dict[str, object]], str | None]:
        try:
            return [self._ui_element_to_dict(element) for element in self._get_state_ui_elements()], None
        except Exception as exc:  # noqa: BLE001
            return [], f"{type(exc).__name__}: {exc}"

    def _get_state_ui_elements(self) -> list[Any]:
        state = self.android_env.get_state(wait_to_stabilize=self.wait_to_stabilize)
        return list(getattr(state, "ui_elements", []) or [])

    def _ui_element_to_dict(self, element: Any) -> dict[str, object]:
        resource_id = getattr(element, "resource_id", None)
        resource_name = getattr(element, "resource_name", None)
        local_id = self._local_resource_name(resource_id or resource_name)
        bbox = getattr(element, "bbox_pixels", None) or getattr(element, "bbox", None)
        bounds = self._bounds_to_list(bbox)
        return {
            "id": local_id,
            "resource_id": resource_id,
            "resource_name": resource_name,
            "text": getattr(element, "text", None) or "",
            "content_description": getattr(element, "content_description", None) or "",
            "class_name": getattr(element, "class_name", None) or "",
            "focused": bool(getattr(element, "is_focused", False)),
            "clickable": bool(getattr(element, "is_clickable", False)),
            "editable": bool(getattr(element, "is_editable", False)),
            "bounds": bounds,
        }

    def _element_matches(self, element: Any, resource_name: str, full_id: str) -> bool:
        values = {
            getattr(element, "resource_id", None),
            getattr(element, "resource_name", None),
        }
        return full_id in values or resource_name in values or any(
            isinstance(value, str) and value.endswith("/" + resource_name) for value in values
        )

    def _local_resource_name(self, raw: str | None) -> str | None:
        if not raw:
            return None
        if "/" in raw:
            return raw.rsplit("/", 1)[-1]
        return raw

    def _bounds_to_list(self, bbox: Any) -> list[float] | None:
        if bbox is None:
            return None
        attrs = ("x_min", "y_min", "x_max", "y_max")
        if all(hasattr(bbox, attr) for attr in attrs):
            return [float(getattr(bbox, attr)) for attr in attrs]
        return None

    def _safe_read_prefs(self) -> str:
        try:
            return self.adb_device.read_shared_prefs()
        except Exception:
            return ""

    def _json_action_module(self) -> Any:
        require_android_world()
        return importlib.import_module("android_world.env.json_action")


def create_native_android_world_env(
    console_port: int = 5554,
    adb_path: str = "adb",
    adb_serial: str | None = None,
    grpc_port: int = 8554,
    task: DummyApkFormSearchTask | None = None,
    max_steps: int | None = None,
    shaped_rewards: bool = True,
    wait_to_stabilize: bool = False,
) -> AndroidWorldDummyApkEnv:
    """Creates a DummyApkEnv using AndroidWorld's controller + AsyncEnv."""

    require_android_world()
    controller_mod = importlib.import_module("android_world.env.android_world_controller")
    interface_mod = importlib.import_module("android_world.env.interface")
    controller = controller_mod.get_controller(
        console_port=console_port,
        adb_path=adb_path,
        grpc_port=grpc_port,
    )
    android_env = interface_mod.AsyncAndroidEnv(controller)
    task = task or DummyApkFormSearchTask()
    return AndroidWorldDummyApkEnv(
        android_env=android_env,
        task=task,
        adb_device=AdbDevice(adb_path=adb_path, package=task.package, serial=adb_serial),
        max_steps=max_steps,
        shaped_rewards=shaped_rewards,
        wait_to_stabilize=wait_to_stabilize,
    )


def make_android_world_agent_class() -> type[Any]:
    """Returns an AndroidWorld EnvironmentInteractingAgent subclass.

    The returned class adapts any repo policy with an `act(observation)` method.
    It is created dynamically so importing this module does not require
    AndroidWorld to be installed.
    """

    require_android_world()
    base_agent = importlib.import_module("android_world.agents.base_agent")

    class DummyApkPolicyAgent(base_agent.EnvironmentInteractingAgent):  # type: ignore[misc]
        def __init__(self, env: Any, policy: Any, task: DummyApkFormSearchTask | None = None, **kwargs: Any) -> None:
            super().__init__(env=env, name="dummy_apk_policy_agent", **kwargs)
            self.task = task or DummyApkFormSearchTask()
            self.policy = policy
            self.adapter = AndroidWorldDummyApkEnv(android_env=env, task=self.task)

        def reset(self, go_home: bool = False) -> None:
            del go_home
            if hasattr(self.policy, "reset"):
                self.policy.reset()
            self.adapter.reset()

        def step(self, goal: str) -> Any:
            observation = self.adapter.observe()
            observation["goal"] = goal
            action = self.policy.act(observation)
            result = self.adapter.step(action)
            return base_agent.AgentInteractionResult(
                done=result.done,
                data={
                    "observation": result.observation,
                    "reward": result.reward,
                    "info": result.info,
                },
            )

    return DummyApkPolicyAgent
