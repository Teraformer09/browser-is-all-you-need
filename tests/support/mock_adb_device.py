"""Test-local ADB-shaped mock device for fast unit coverage."""

from __future__ import annotations

from dataclasses import dataclass

from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


@dataclass
class MockUiNode:
    resource_id: str
    text: str
    bounds: tuple[int, int, int, int]
    focused: bool = False

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)


class MockAdbDevice:
    name = "adb"

    def __init__(self, task: DummyApkFormSearchTask | None = None, **kwargs: object) -> None:
        del kwargs
        self.task = task or DummyApkFormSearchTask()
        self.snapshots: dict[str, dict[str, object]] = {}
        self.fail_snapshot_restore = False
        self.reset_state()

    def reset_state(self) -> None:
        self.episode_id = ""
        self.query = ""
        self.name_text = ""
        self.email = ""
        self.submitted = False
        self.pickup = "Current location"
        self.destination = ""
        self.ride_type = ""
        self.cab_type = ""
        self.payment = ""
        self.coupon = ""
        self.journey_stage = 0
        self.sequence_error = False
        self.ride_confirmed = False
        self.ride_cancelled = False
        self.screen = "ride"
        self.focus = None
        self.last_tap: tuple[int, int] | None = None
        self.updated_at_ms = 0
        self.seed = getattr(self.task, "seed", 0)
        self.debug_state_text = "{}"

    def connect(self) -> None:
        return None

    def wait_for_ready(self, timeout_s: int = 180) -> None:
        del timeout_s

    def wait_for_device(self) -> None:
        return None

    def force_stop(self) -> None:
        return None

    def clear_app_data(self) -> None:
        self.reset_state()

    def install_apk(self, apk_path: str) -> None:
        del apk_path

    def launch_app(self, episode_id: str | None = None, extras: dict[str, str | int | bool] | None = None) -> None:
        self.episode_id = episode_id or ""
        extras = extras or {}
        self.seed = int(extras.get("seed", getattr(self.task, "seed", 0)))
        self.screen = str(extras.get("start_screen", "ride"))
        self._touch_state()

    def reset_app(self, episode_id: str | None = None, extras: dict[str, str | int | bool] | None = None) -> None:
        self.clear_app_data()
        self.launch_app(episode_id=episode_id, extras=extras)

    def snapshot_exists(self, snapshot_name: str) -> bool:
        return snapshot_name in self.snapshots

    def supports_emulator_console(self) -> bool:
        return True

    def save_snapshot(self, snapshot_name: str) -> None:
        self.snapshots[snapshot_name] = self._capture_state()

    def restore_snapshot(self, snapshot_name: str) -> None:
        if self.fail_snapshot_restore:
            raise RuntimeError("forced snapshot restore failure")
        if snapshot_name not in self.snapshots:
            raise RuntimeError(f"missing snapshot: {snapshot_name}")
        self._restore_state(self.snapshots[snapshot_name])

    def wait_for_ui_ready(self) -> None:
        return None

    def click_resource(self, resource_name: str) -> None:
        if resource_name in {"search_input", "name_input", "email_input"}:
            self.focus = resource_name
        elif resource_name == "search_button":
            self.screen = "form"
        elif resource_name == "clear_button":
            self.clear_app_data()
        elif resource_name == "submit_button":
            if self.name_text and self.email:
                self.submitted = True
                self.screen = "submitted"
            else:
                self.submitted = False
                self.screen = "validation_error"
        elif resource_name == "ride_type_ride":
            self.ride_type = "Ride"
            self._advance_stage(1, "ride_type")
        elif resource_name == "ride_type_reserve":
            self.ride_type = "Reserve"
            self._advance_stage(1, "ride_type")
        elif resource_name == "ride_type_premium":
            self.ride_type = "Premium"
            self._advance_stage(1, "ride_type")
        elif resource_name == "ride_option_mini":
            self.cab_type = "Mini"
            self._advance_stage(3, "cab_type")
        elif resource_name == "ride_option_sedan":
            self.cab_type = "Sedan"
            self._advance_stage(3, "cab_type")
        elif resource_name == "ride_option_premium":
            self.cab_type = "Premium"
            self._advance_stage(3, "cab_type")
        elif resource_name == "location_suggestion_1":
            self.screen = "destination_suggestions"
        elif resource_name == "location_suggestion_2":
            self.screen = "destination_suggestions"
        elif resource_name == "destination_search_button":
            if self.destination and not self.sequence_error and self.journey_stage == 1:
                self.journey_stage = 2
                self.screen = "destination"
            else:
                self.sequence_error = True
                self.screen = "ride_validation_error"
        elif resource_name == "apply_coupon_button":
            self.focus = "coupon_input"
            self.screen = "coupon"
        elif resource_name == "coupon_apply_button":
            self.screen = "coupon"
        elif resource_name == "payment_cash":
            self.payment = "cash"
            self._advance_stage(4, "payment")
        elif resource_name == "payment_card":
            self.payment = "card"
            self._advance_stage(4, "payment")
        elif resource_name == "payment_upi":
            self.payment = "upi"
            self._advance_stage(4, "payment")
        elif resource_name == "confirm_ride_button":
            if self.journey_stage >= 4 and not self.sequence_error:
                self.ride_confirmed = True
                self.ride_cancelled = False
                self.journey_stage = 5
                self.screen = "ride_booked"
            else:
                self.sequence_error = True
                self.ride_confirmed = False
                self.screen = "ride_validation_error"
        elif resource_name == "cancel_ride_button":
            self.ride_cancelled = True
            self.ride_confirmed = False
            self.journey_stage = 5
            self.screen = "ride_cancelled"
        self._touch_state()

    def input_resource(self, resource_name: str, text: str) -> None:
        self.focus = resource_name
        if resource_name == "search_input":
            self.query = text
        elif resource_name == "name_input":
            self.name_text = text
        elif resource_name == "email_input":
            self.email = text
        elif resource_name == "pickup_input":
            self.pickup = text
        elif resource_name == "drop_input":
            self.destination = text
            self.screen = "destination"
        elif resource_name == "coupon_input":
            self.coupon = text
        self._touch_state()

    def press_back(self) -> None:
        self.focus = None

    def press_home(self) -> None:
        self.focus = None

    def tap_coordinates(self, x: int, y: int) -> None:
        self.last_tap = (x, y)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        del x1, y1, x2, y2, duration_ms

    def dump_ui(self) -> str:
        return "<hierarchy />"

    def find_resource(self, resource_name: str) -> MockUiNode:
        for node in self.dump_resource_nodes((resource_name,)):
            if node["id"] == resource_name:
                bounds = tuple(int(value) for value in (node.get("bounds") or [0, 0, 10, 10]))
                return MockUiNode(
                    resource_id=str(node["resource_id"]),
                    text=str(node.get("text", "")),
                    bounds=bounds,  # type: ignore[arg-type]
                    focused=bool(node.get("focused", False)),
                )
        raise LookupError(f"resource not found: {resource_name}")

    def dump_resource_nodes(self, resource_names: tuple[str, ...]) -> list[dict[str, object]]:
        values = {
            "search_input": self.query,
            "search_button": "Search",
            "search_result": f"Search result: {self.query}" if self.query else "Search result: none",
            "name_input": self.name_text,
            "email_input": self.email,
            "submit_button": "Submit Form",
            "clear_button": "Clear",
            "status_text": self.status_text(),
            "pickup_input": self.pickup,
            "drop_input": self.destination,
            "location_suggestion_1": "Airport",
            "location_suggestion_2": "City Center",
            "destination_search_button": "Search Destination",
            "ride_type_ride": "Ride",
            "ride_type_reserve": "Reserve",
            "ride_type_premium": "Premium",
            "ride_option_mini": "Mini",
            "ride_option_sedan": "Sedan",
            "ride_option_premium": "Premium",
            "apply_coupon_button": "Apply Coupon",
            "coupon_input": self.coupon,
            "coupon_apply_button": "Save Coupon",
            "payment_cash": "Cash",
            "payment_card": "Card",
            "payment_upi": "UPI",
            "confirm_ride_button": "Book Ride",
            "cancel_ride_button": "Cancel Ride",
            "final_status_text": self.ride_status_text(),
            "route_summary_text": self.route_summary_text(),
            "ride_progress_text": self.ride_progress_text(),
            "ride_debug_state_text": self.debug_state_text,
        }
        return [
            {
                "id": name,
                "element_index": index,
                "resource_id": f"{self.task.package}:id/{name}",
                "text": values.get(name, ""),
                "focused": self.focus == name,
                "bounds": [0, 0, 10, 10],
                "center": [5, 5],
                "class_name": "android.widget.EditText" if name.endswith("_input") else "android.widget.TextView",
                "clickable": not name.endswith("_text"),
            }
            for index, name in enumerate(resource_names)
        ]

    def read_shared_prefs(self) -> str:
        if not (self.episode_id or self.query or self.name_text or self.email or self.submitted):
            return ""
        submitted = "true" if self.submitted else "false"
        ride_confirmed = "true" if self.ride_confirmed else "false"
        ride_cancelled = "true" if self.ride_cancelled else "false"
        sequence_error = "true" if self.sequence_error else "false"
        return f"""<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<map>
    <string name="episode_id">{self.episode_id}</string>
    <boolean name="submitted" value="{submitted}" />
    <string name="query">{self.query}</string>
    <string name="name">{self.name_text}</string>
    <string name="email">{self.email}</string>
    <string name="ride_pickup">{self.pickup}</string>
    <string name="ride_drop">{self.destination}</string>
    <string name="destination_query">{self.destination}</string>
    <string name="ride_type">{self.ride_type}</string>
    <string name="selected_ride">{self.cab_type}</string>
    <string name="selected_cab_type">{self.cab_type}</string>
    <string name="payment">{self.payment}</string>
    <string name="payment_type">{self.payment}</string>
    <string name="coupon">{self.coupon}</string>
    <int name="journey_stage" value="{self.journey_stage}" />
    <boolean name="sequence_error" value="{sequence_error}" />
    <boolean name="ride_confirmed" value="{ride_confirmed}" />
    <boolean name="ride_cancelled" value="{ride_cancelled}" />
    <string name="screen">{self.screen}</string>
    <long name="updated_at_ms" value="{self.updated_at_ms}" />
    <int name="seed" value="{self.seed}" />
</map>
"""

    def status_text(self) -> str:
        if self.submitted:
            return f"Status: submitted {self.name_text} <{self.email}>"
        if self.query:
            return f"Status: search {self.query}"
        return "Status: waiting"

    def ride_status_text(self) -> str:
        if self.ride_cancelled:
            return f"Ride cancelled on stage {self.journey_stage}"
        if self.ride_confirmed:
            return f"Ride booked: {self.ride_type} / {self.cab_type} / {self.payment}"
        if self.sequence_error:
            return "Ride status: sequence error"
        return "Ride status: choose a ride type"

    def route_summary_text(self) -> str:
        return (
            f"Pickup={self.pickup} | Ride={self.ride_type or 'not set'} | "
            f"Destination={self.destination or 'not set'} | Cab={self.cab_type or 'not set'} | "
            f"Payment={self.payment or 'not set'}"
        )

    def ride_progress_text(self) -> str:
        return f"Step {self.journey_stage}/5"

    def _advance_stage(self, expected_stage: int, event: str) -> None:
        if self.sequence_error:
            return
        if self.journey_stage == expected_stage - 1:
            self.journey_stage = expected_stage
            self.screen = event
        else:
            self.sequence_error = True
            self.screen = "ride_validation_error"

    def _capture_state(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "query": self.query,
            "name_text": self.name_text,
            "email": self.email,
            "submitted": self.submitted,
            "pickup": self.pickup,
            "destination": self.destination,
            "ride_type": self.ride_type,
            "cab_type": self.cab_type,
            "payment": self.payment,
            "coupon": self.coupon,
            "journey_stage": self.journey_stage,
            "sequence_error": self.sequence_error,
            "ride_confirmed": self.ride_confirmed,
            "ride_cancelled": self.ride_cancelled,
            "screen": self.screen,
            "updated_at_ms": self.updated_at_ms,
            "seed": self.seed,
            "debug_state_text": self.debug_state_text,
        }

    def _restore_state(self, state: dict[str, object]) -> None:
        self.episode_id = str(state.get("episode_id", ""))
        self.query = str(state.get("query", ""))
        self.name_text = str(state.get("name_text", ""))
        self.email = str(state.get("email", ""))
        self.submitted = bool(state.get("submitted", False))
        self.pickup = str(state.get("pickup", "Current location"))
        self.destination = str(state.get("destination", ""))
        self.ride_type = str(state.get("ride_type", ""))
        self.cab_type = str(state.get("cab_type", ""))
        self.payment = str(state.get("payment", ""))
        self.coupon = str(state.get("coupon", ""))
        self.journey_stage = int(state.get("journey_stage", 0))
        self.sequence_error = bool(state.get("sequence_error", False))
        self.ride_confirmed = bool(state.get("ride_confirmed", False))
        self.ride_cancelled = bool(state.get("ride_cancelled", False))
        self.screen = str(state.get("screen", "ride"))
        self.updated_at_ms = int(state.get("updated_at_ms", 0))
        self.seed = int(state.get("seed", 0))
        self.debug_state_text = str(state.get("debug_state_text", "{}"))

    def _touch_state(self) -> None:
        self.updated_at_ms += 1
        self.debug_state_text = self.route_summary_text()
