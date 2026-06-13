"""Ride-booking dummy APK task and reward verifier."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.tasks.dummy_apk import new_episode_id


@dataclass(frozen=True)
class RideBookingTask:
    pickup: str = "Sector 62"
    drop: str = "Noida City Centre"
    selected_ride: str = "Mini"
    payment: str = ""
    coupon: str = ""
    cancel_after_assignment: bool = False
    package: str = "com.primeintellect.dummyrl"
    name_label: str = "RideBookingTask"
    max_steps: int = 15
    task_id: str = "ride_cheapest_001"
    episode_id: str = field(default_factory=lambda: new_episode_id("ride_cheapest_001"))
    surface: str = "android_apk"
    difficulty: str = "medium"
    seed: int = 2001

    @property
    def resource_names(self) -> tuple[str, ...]:
        return (
            "pickup_input",
            "drop_input",
            "location_suggestion_1",
            "location_suggestion_2",
            "ride_option_mini",
            "ride_option_sedan",
            "ride_option_premium",
            "cheapest_badge",
            "apply_coupon_button",
            "coupon_input",
            "coupon_apply_button",
            "payment_cash",
            "payment_upi",
            "confirm_ride_button",
            "cancel_ride_button",
            "final_status_text",
        )

    @property
    def goal(self) -> str:
        if self.cancel_after_assignment:
            return f"Book then cancel a {self.selected_ride} ride from {self.pickup} to {self.drop}."
        return f"Book a {self.selected_ride} ride from {self.pickup} to {self.drop}."

    def expected_state(self) -> dict[str, str]:
        expected = {
            "episode_id": self.episode_id,
            "ride_pickup": self.pickup,
            "ride_drop": self.drop,
            "selected_ride": self.selected_ride,
        }
        if self.payment:
            expected["payment"] = self.payment
        if self.coupon:
            expected["coupon"] = self.coupon
        if self.cancel_after_assignment:
            expected["ride_cancelled"] = "true"
            expected["screen"] = "ride_cancelled"
        else:
            expected["ride_confirmed"] = "true"
            expected["screen"] = "driver_assigned"
        return expected

    def new_episode(self) -> "RideBookingTask":
        return replace(self, episode_id=new_episode_id(self.task_id))

    def launch_extras(self) -> dict[str, str | int | bool]:
        return {"episode_id": self.episode_id, "seed": self.seed, "start_screen": "home"}

    def initialize_task(self, device: Any) -> None:
        del device

    def reset_episode(self, device: Any) -> None:
        del device

    def verify_success(self, observation: dict[str, Any]) -> bool:
        return bool(observation.get("exact_success", False))

    def teardown_task(self, device: Any) -> None:
        del device

    def run_scripted(self, device: AdbDevice) -> dict[str, Any]:
        device.reset_app(episode_id=self.episode_id, extras=self.launch_extras())

        trajectory: list[dict[str, str]] = []
        self._record(trajectory, "input_resource", "pickup_input", self.pickup)
        device.input_resource("pickup_input", self.pickup)
        device.press_back()
        self._record(trajectory, "input_resource", "drop_input", self.drop)
        device.input_resource("drop_input", self.drop)
        device.press_back()

        ride_target = {
            "Mini": "ride_option_mini",
            "Sedan": "ride_option_sedan",
            "Premium": "ride_option_premium",
        }[self.selected_ride]
        self._record(trajectory, "click_resource", ride_target)
        device.click_resource(ride_target)
        device.swipe(540, 2100, 540, 1200, 400)

        if self.coupon:
            self._record(trajectory, "click_resource", "apply_coupon_button")
            device.click_resource("apply_coupon_button")
            self._record(trajectory, "input_resource", "coupon_input", self.coupon)
            device.input_resource("coupon_input", self.coupon)
            self._record(trajectory, "click_resource", "coupon_apply_button")
            device.click_resource("coupon_apply_button")

        if self.payment:
            payment_target = f"payment_{self.payment}"
            self._record(trajectory, "click_resource", payment_target)
            device.click_resource(payment_target)

        self._record(trajectory, "click_resource", "confirm_ride_button")
        device.click_resource("confirm_ride_button")

        if self.cancel_after_assignment:
            self._record(trajectory, "click_resource", "cancel_ride_button")
            device.click_resource("cancel_ride_button")

        prefs = device.read_shared_prefs()
        reward = self.reward_from_prefs(prefs)
        status_node = device.find_resource("final_status_text")

        return {
            "task": self.name_label,
            "task_id": self.task_id,
            "episode_id": self.episode_id,
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

    def reward_components_from_prefs(
        self,
        prefs_xml: str,
        *,
        no_forbidden_action: bool = True,
        no_invalid_action: bool = True,
        finish_after_success: bool = True,
    ) -> dict[str, bool]:
        del no_forbidden_action, no_invalid_action, finish_after_success
        state = self.state_from_prefs(prefs_xml)
        return {key: state.get(key) == value for key, value in self.expected_state().items()}

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
        if not components:
            return 0.0
        return sum(1 for passed in components.values() if passed) / len(components)

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
        return 1.0 if components and all(components.values()) else 0.0

    def action_sequence(self) -> list[dict[str, Any]]:
        ride_target = {
            "Mini": "ride_option_mini",
            "Sedan": "ride_option_sedan",
            "Premium": "ride_option_premium",
        }[self.selected_ride]
        actions: list[dict[str, Any]] = [
            {"type": "type_text", "element_id": "pickup_input", "text": self.pickup},
            {"type": "type_text", "element_id": "drop_input", "text": self.drop},
            {"type": "tap_element", "element_id": ride_target, "text": None},
        ]
        if self.coupon:
            actions.extend(
                [
                    {"type": "tap_element", "element_id": "apply_coupon_button", "text": None},
                    {"type": "type_text", "element_id": "coupon_input", "text": self.coupon},
                    {"type": "tap_element", "element_id": "coupon_apply_button", "text": None},
                ]
            )
        if self.payment:
            actions.append({"type": "tap_element", "element_id": f"payment_{self.payment}", "text": None})
        actions.append({"type": "tap_element", "element_id": "confirm_ride_button", "text": None})
        if self.cancel_after_assignment:
            actions.append({"type": "tap_element", "element_id": "cancel_ride_button", "text": None})
        return [_complete_action(action) for action in actions]

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


def _complete_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": action["type"],
        "element_id": action.get("element_id"),
        "text": action.get("text"),
        "x": None,
        "y": None,
        "x1": None,
        "y1": None,
        "x2": None,
        "y2": None,
        "duration_ms": None,
    }
