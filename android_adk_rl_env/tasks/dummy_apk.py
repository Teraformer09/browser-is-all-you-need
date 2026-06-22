"""ADB-backed RL task for the real dummy Android APK."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.core.task import DEFAULT_FORM_RANDOMIZATION, DEFAULT_FORM_REWARD_WEIGHTS, DEFAULT_SAFETY
from android_adk_rl_env.reset_manager import reset_task_device


@dataclass(frozen=True)
class DummyApkFormSearchTask:
    """Search, fill a form, submit it, and validate durable APK state."""

    query: str = "airport ride"
    name: str = "Ada Lovelace"
    email: str = "ada@example.com"
    package: str = "com.primeintellect.dummyrl"
    name_label: str = "DummyApkFormSearchTask"
    max_steps: int = 10
    task_id: str = "form_submit_001"
    surface: str = "android_apk"
    start_screen: str = "home"
    seed: int = 1001
    difficulty: str = "easy"
    randomization: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_FORM_RANDOMIZATION))
    safety: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SAFETY))
    reward_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_FORM_REWARD_WEIGHTS))
    episode_id: str = field(default_factory=lambda: new_episode_id("form_submit_001"))

    @property
    def resource_names(self) -> tuple[str, ...]:
        return (
            "search_input",
            "search_button",
            "search_result",
            "name_input",
            "email_input",
            "submit_button",
            "clear_button",
            "status_text",
            "debug_state_text",
        )

    @property
    def goal(self) -> str:
        return (
            "In Dummy RL App, search for "
            f"{self.query!r}, enter name {self.name!r}, enter email {self.email!r}, "
            "and submit the form."
        )

    def expected_state(self) -> dict[str, str]:
        return {
            "episode_id": self.episode_id,
            "query": self.query,
            "name": self.name,
            "email": self.email,
            "submitted": "true",
            "screen": "submitted",
        }

    def new_episode(self) -> "DummyApkFormSearchTask":
        return replace(self, episode_id=new_episode_id(self.task_id))

    def launch_extras(self) -> dict[str, str | int | bool]:
        randomization = {**DEFAULT_FORM_RANDOMIZATION, **self.randomization}
        delay_ms = randomization.get("network_delay_ms", [0, 0])
        delay_min, delay_max = (delay_ms + [0, 0])[:2] if isinstance(delay_ms, list) else (0, 0)
        return {
            "episode_id": self.episode_id,
            "seed": int(self.seed),
            "start_screen": self.start_screen,
            "randomization_enabled": bool(randomization.get("enabled", False)),
            "button_text_variant": bool(randomization.get("button_text_variant", False)),
            "field_order_variant": bool(randomization.get("field_order_variant", False)),
            "theme_variant": bool(randomization.get("theme_variant", False)),
            "start_screen_variant": bool(randomization.get("start_screen_variant", False)),
            "network_delay_min_ms": int(delay_min),
            "network_delay_max_ms": int(delay_max),
        }

    def initialize_task(self, device: Any) -> None:
        del device

    def reset_episode(self, device: Any) -> None:
        del device

    def verify_success(self, observation: dict[str, Any]) -> bool:
        return bool(observation.get("exact_success", False))

    def teardown_task(self, device: Any) -> None:
        del device

    def run_scripted(self, device: AdbDevice) -> dict[str, Any]:
        reset_metadata = reset_task_device(self, device).to_dict()

        trajectory: list[dict[str, str]] = []
        self._record(trajectory, "input_resource", "search_input", self.query)
        device.input_resource("search_input", self.query)
        self._record(trajectory, "click_resource", "search_button")
        device.click_resource("search_button")

        self._record(trajectory, "input_resource", "name_input", self.name)
        device.input_resource("name_input", self.name)
        self._record(trajectory, "input_resource", "email_input", self.email)
        device.input_resource("email_input", self.email)
        device.press_back()

        self._record(trajectory, "click_resource", "submit_button")
        try:
            device.click_resource("submit_button")
        except LookupError:
            email_node = device.find_resource("email_input")
            x, _ = email_node.center
            _, _, _, bottom = email_node.bounds
            device.tap_coordinates(x, bottom + 60)

        prefs = device.read_shared_prefs()
        reward = self.shaped_reward_from_prefs(prefs)
        final_reward = self.reward_from_prefs(prefs)
        reward_components = self.reward_components_from_prefs(prefs)
        try:
            status_text = device.find_resource("status_text").text
        except LookupError:
            status_text = ""

        return {
            "task": self.name_label,
            "task_id": self.task_id,
            "episode_id": self.episode_id,
            "goal": self.goal,
            "package": self.package,
            "success": final_reward >= 1.0,
            "reward": reward,
            "final_reward": final_reward,
            "reward_components": reward_components,
            "reset_metadata": reset_metadata,
            "status_text": status_text,
            "shared_prefs": prefs,
            "trajectory": trajectory,
        }

    def state_from_prefs(self, prefs_xml: str) -> dict[str, str]:
        if not prefs_xml.strip():
            return {}
        try:
            root = ET.fromstring(prefs_xml)
        except ET.ParseError:
            return {}

        state: dict[str, str] = {}
        for elem in root:
            name = elem.attrib.get("name")
            if not name:
                continue
            if elem.tag == "string":
                state[name] = elem.text or ""
            elif elem.tag == "boolean":
                state[name] = elem.attrib.get("value", "")
            elif elem.tag == "long":
                state[name] = elem.attrib.get("value", "")
            elif elem.tag == "int":
                state[name] = elem.attrib.get("value", "")
        return state

    def reward_components_from_prefs(
        self,
        prefs_xml: str,
        *,
        no_forbidden_action: bool = True,
        no_invalid_action: bool = True,
        finish_after_success: bool = True,
    ) -> dict[str, bool]:
        state = self.state_from_prefs(prefs_xml)
        if not state:
            return {
                "episode_match": False,
                "screen_match": False,
                "query_match": False,
                "name_match": False,
                "email_match": False,
                "submitted": False,
                "no_forbidden_action": False,
                "no_invalid_action": False,
                "finish_after_success": False,
            }
        expected = self.expected_state()
        return {
            "episode_match": state.get("episode_id") == expected["episode_id"],
            "screen_match": state.get("screen") == expected["screen"],
            "query_match": state.get("query") == expected["query"],
            "name_match": state.get("name") == expected["name"],
            "email_match": state.get("email") == expected["email"],
            "submitted": state.get("submitted") == expected["submitted"],
            "no_forbidden_action": no_forbidden_action,
            "no_invalid_action": no_invalid_action,
            "finish_after_success": finish_after_success,
        }

    def exact_success_from_components(self, components: dict[str, bool]) -> bool:
        required = (
            "episode_match",
            "screen_match",
            "query_match",
            "name_match",
            "email_match",
            "submitted",
            "no_forbidden_action",
            "no_invalid_action",
        )
        return bool(components) and all(components.get(key, False) for key in required)

    def shaped_reward_from_components(self, components: dict[str, bool]) -> float:
        if not components:
            return 0.0
        weights = {**DEFAULT_FORM_REWARD_WEIGHTS, **self.reward_weights}
        total_weight = sum(float(weight) for weight in weights.values())
        if total_weight <= 0:
            return 0.0
        score = sum(float(weights.get(key, 0.0)) for key, passed in components.items() if passed)
        return score / total_weight

    def shaped_reward_from_prefs(
        self,
        prefs_xml: str,
        *,
        no_forbidden_action: bool = True,
        no_invalid_action: bool = True,
        finish_after_success: bool = True,
    ) -> float:
        components = self.reward_components_from_prefs(
            prefs_xml,
            no_forbidden_action=no_forbidden_action,
            no_invalid_action=no_invalid_action,
            finish_after_success=finish_after_success,
        )
        return self.shaped_reward_from_components(components)

    def reward_from_prefs(
        self,
        prefs_xml: str,
        *,
        no_forbidden_action: bool = True,
        no_invalid_action: bool = True,
        finish_after_success: bool = True,
    ) -> float:
        components = self.reward_components_from_prefs(
            prefs_xml,
            no_forbidden_action=no_forbidden_action,
            no_invalid_action=no_invalid_action,
            finish_after_success=finish_after_success,
        )
        return 1.0 if self.exact_success_from_components(components) else 0.0

    def _record(
        self,
        trajectory: list[dict[str, str]],
        action: str,
        target: str,
        text: str | None = None,
    ) -> None:
        entry = {"action": action, "target": target}
        if text is not None:
            entry["text"] = text
        trajectory.append(entry)


def new_episode_id(task_id: str = "task") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ep_{task_id}_{timestamp}_{uuid4().hex[:8]}"
