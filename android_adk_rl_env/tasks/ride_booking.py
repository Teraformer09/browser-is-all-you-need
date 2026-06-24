"""Ride-booking dummy APK task and reward verifier."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.core.task import DEFAULT_RIDE_REWARD_WEIGHTS
from android_adk_rl_env.reset_manager import reset_task_device
from android_adk_rl_env.tasks.dummy_apk import new_episode_id


@dataclass(frozen=True)
class RideBookingTask:
    pickup: str = "Current location"
    ride_type: str = "Ride"
    destination: str = "Noida City Centre"
    selected_ride: str = "Mini"
    payment: str = "upi"
    coupon: str = ""
    cancel_after_assignment: bool = False
    package: str = "com.primeintellect.dummyrl"
    name_label: str = "RideBookingTask"
    max_steps: int = 15
    task_id: str = "ride_clone_001"
    episode_id: str = field(default_factory=lambda: new_episode_id("ride_clone_001"))
    surface: str = "android_apk"
    difficulty: str = "medium"
    seed: int = 2001
    reward_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_RIDE_REWARD_WEIGHTS))

    @property
    def resource_names(self) -> tuple[str, ...]:
        return (
            "pickup_input",
            "drop_input",
            "destination_search_button",
            "location_suggestion_1",
            "location_suggestion_2",
            "ride_type_ride",
            "ride_type_reserve",
            "ride_type_premium",
            "ride_option_mini",
            "ride_option_sedan",
            "ride_option_premium",
            "payment_cash",
            "payment_card",
            "payment_upi",
            "confirm_ride_button",
            "cancel_ride_button",
            "final_status_text",
            "route_summary_text",
            "ride_progress_text",
            "ride_debug_state_text",
        )

    @property
    def goal(self) -> str:
        base = (
            f"Choose {self.ride_type} ride from {self.pickup} to {self.destination}, "
            f"select {self.selected_ride}, and pay with {self.payment}."
        )
        if self.cancel_after_assignment:
            return base[:-1] + " and cancel after assignment."
        return base[:-1] + " and confirm the booking."

    def expected_state(self) -> dict[str, str]:
        expected = {
            "episode_id": self.episode_id,
            "ride_pickup": self.pickup,
            "ride_type": self.ride_type,
            "ride_drop": self.destination,
            "selected_ride": self.selected_ride,
            "payment": self.payment,
            "journey_stage": "5",
            "sequence_error": "false",
        }
        if self.cancel_after_assignment:
            expected["ride_cancelled"] = "true"
            expected["screen"] = "ride_cancelled"
        else:
            expected["ride_confirmed"] = "true"
            expected["screen"] = "ride_booked"
        return expected

    def new_episode(self) -> "RideBookingTask":
        return replace(self, episode_id=new_episode_id(self.task_id))

    def launch_extras(self) -> dict[str, str | int | bool]:
        return {"episode_id": self.episode_id, "seed": self.seed, "start_screen": "ride"}

    def initialize_task(self, device: Any) -> None:
        del device

    def reset_episode(self, device: Any) -> None:
        # The ride screen now opens directly on the booking surface.
        del device

    def verify_success(self, observation: dict[str, Any]) -> bool:
        return bool(observation.get("exact_success", False))

    def teardown_task(self, device: Any) -> None:
        del device

    def run_scripted(self, device: AdbDevice) -> dict[str, Any]:
        reset_metadata = reset_task_device(self, device).to_dict()

        trajectory: list[dict[str, str]] = []
        if self.pickup:
            self._record(trajectory, "input_resource", "pickup_input", self.pickup)
            device.input_resource("pickup_input", self.pickup)
            device.press_back()

        ride_type_target = {
            "Ride": "ride_type_ride",
            "Reserve": "ride_type_reserve",
            "Premium": "ride_type_premium",
        }.get(self.ride_type, "ride_type_ride")
        self._record(trajectory, "click_resource", ride_type_target)
        device.click_resource(ride_type_target)

        self._record(trajectory, "input_resource", "drop_input", self.destination)
        device.input_resource("drop_input", self.destination)
        device.press_back()
        self._record(trajectory, "click_resource", "destination_search_button")
        device.click_resource("destination_search_button")

        ride_target = {
            "Mini": "ride_option_mini",
            "Sedan": "ride_option_sedan",
            "Premium": "ride_option_premium",
        }.get(self.selected_ride, "ride_option_mini")
        self._record(trajectory, "click_resource", ride_target)
        device.click_resource(ride_target)
        device.swipe(540, 2100, 540, 1200, 400)

        if self.coupon:
            self._record(trajectory, "click_resource", "location_suggestion_1")
            device.click_resource("location_suggestion_1")
            self._record(trajectory, "input_resource", "coupon_input", self.coupon)
            device.input_resource("coupon_input", self.coupon)
            self._record(trajectory, "click_resource", "location_suggestion_2")
            device.click_resource("location_suggestion_2")

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
        reward = self.shaped_reward_from_prefs(prefs, finish_after_success=False)
        final_reward = self.reward_from_prefs(prefs, finish_after_success=False)
        reward_components = self.reward_components_from_prefs(prefs, finish_after_success=False)
        try:
            status_text = device.find_resource("final_status_text").text
        except LookupError:
            status_text = ""
        try:
            route_summary_text = device.find_resource("route_summary_text").text
        except LookupError:
            route_summary_text = ""

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
            "route_summary_text": route_summary_text,
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
                "pickup_match": False,
                "ride_type_match": False,
                "destination_match": False,
                "cab_type_match": False,
                "payment_match": False,
                "journey_stage_match": False,
                "screen_match": False,
                "ride_terminal_state": False,
                "sequence_clean": False,
                "no_forbidden_action": False,
                "no_invalid_action": False,
                "finish_after_success": False,
            }
        expected = self.expected_state()
        terminal_key = "ride_cancelled" if self.cancel_after_assignment else "ride_confirmed"
        terminal_value = expected.get(terminal_key, "false")
        return {
            "episode_match": state.get("episode_id") == expected["episode_id"],
            "pickup_match": state.get("ride_pickup") == expected["ride_pickup"],
            "ride_type_match": state.get("ride_type") == expected["ride_type"],
            "destination_match": state.get("ride_drop") == expected["ride_drop"],
            "cab_type_match": state.get("selected_ride") == expected["selected_ride"],
            "payment_match": state.get("payment") == expected["payment"],
            "journey_stage_match": state.get("journey_stage") == expected["journey_stage"],
            "screen_match": state.get("screen") == expected["screen"],
            "ride_terminal_state": state.get(terminal_key) == terminal_value,
            "sequence_clean": state.get("sequence_error") == expected["sequence_error"],
            "no_forbidden_action": no_forbidden_action,
            "no_invalid_action": no_invalid_action,
            "finish_after_success": finish_after_success,
        }

    def exact_success_from_components(self, components: dict[str, bool]) -> bool:
        required = (
            "episode_match",
            "pickup_match",
            "ride_type_match",
            "destination_match",
            "cab_type_match",
            "payment_match",
            "journey_stage_match",
            "screen_match",
            "ride_terminal_state",
            "sequence_clean",
            "no_forbidden_action",
            "no_invalid_action",
        )
        return bool(components) and all(components.get(key, False) for key in required)

    def shaped_reward_from_components(self, components: dict[str, bool]) -> float:
        if not components:
            return 0.0
        weights = {**DEFAULT_RIDE_REWARD_WEIGHTS, **self.reward_weights}
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

    def action_sequence(self) -> list[dict[str, Any]]:
        ride_type_target = {
            "Ride": "ride_type_ride",
            "Reserve": "ride_type_reserve",
            "Premium": "ride_type_premium",
        }.get(self.ride_type, "ride_type_ride")
        ride_target = {
            "Mini": "ride_option_mini",
            "Sedan": "ride_option_sedan",
            "Premium": "ride_option_premium",
        }.get(self.selected_ride, "ride_option_mini")
        actions: list[dict[str, Any]] = []
        if self.pickup:
            actions.append({"type": "type_text", "element_id": "pickup_input", "text": self.pickup})
        actions.extend(
            [
                {"type": "tap_element", "element_id": ride_type_target, "text": None},
                {"type": "type_text", "element_id": "drop_input", "text": self.destination},
                {"type": "tap_element", "element_id": "destination_search_button", "text": None},
                {"type": "tap_element", "element_id": ride_target, "text": None},
            ]
        )
        if self.coupon:
            actions.extend(
                [
                    {"type": "tap_element", "element_id": "location_suggestion_1", "text": None},
                    {"type": "type_text", "element_id": "coupon_input", "text": self.coupon},
                    {"type": "tap_element", "element_id": "location_suggestion_2", "text": None},
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
