"""ADB-backed RL task for the real dummy Android APK."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice


@dataclass(frozen=True)
class DummyApkFormSearchTask:
    """Search, fill a form, submit it, and validate durable APK state."""

    query: str = "airport ride"
    name: str = "Ada Lovelace"
    email: str = "ada@example.com"
    package: str = "com.primeintellect.dummyrl"
    name_label: str = "DummyApkFormSearchTask"
    max_steps: int = 10

    @property
    def resource_names(self) -> tuple[str, ...]:
        return (
            "search_input",
            "search_button",
            "search_result",
            "name_input",
            "email_input",
            "submit_button",
            "status_text",
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
            "query": self.query,
            "name": self.name,
            "email": self.email,
            "submitted": "true",
        }

    def run_scripted(self, device: AdbDevice) -> dict[str, Any]:
        device.wait_for_device()
        device.clear_app_data()
        device.launch_app()

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
        device.click_resource("submit_button")

        prefs = device.read_shared_prefs()
        reward = self.reward_from_prefs(prefs)
        status_node = device.find_resource("status_text")

        return {
            "task": self.name_label,
            "goal": self.goal,
            "package": self.package,
            "success": reward >= 1.0,
            "reward": reward,
            "status_text": status_node.text,
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
        return state

    def reward_components_from_prefs(self, prefs_xml: str) -> dict[str, bool]:
        state = self.state_from_prefs(prefs_xml)
        expected = self.expected_state()
        return {key: state.get(key) == value for key, value in expected.items()}

    def shaped_reward_from_prefs(self, prefs_xml: str) -> float:
        components = self.reward_components_from_prefs(prefs_xml)
        if not components:
            return 0.0
        return sum(1 for passed in components.values() if passed) / len(components)

    def reward_from_prefs(self, prefs_xml: str) -> float:
        components = self.reward_components_from_prefs(prefs_xml)
        return 1.0 if components and all(components.values()) else 0.0

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
