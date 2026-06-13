"""Test-local ADB-shaped mock device for fast unit coverage."""

from __future__ import annotations

import json
import time

from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


class MockAdbDevice:
    name = "adb"

    def __init__(self, task: DummyApkFormSearchTask | None = None, **kwargs: object) -> None:
        del kwargs
        self.task = task or DummyApkFormSearchTask()
        self.reset_state()

    def reset_state(self) -> None:
        self.episode_id = ""
        self.query = ""
        self.name_text = ""
        self.email = ""
        self.submitted = False
        self.ride_pickup = ""
        self.ride_drop = ""
        self.selected_ride = ""
        self.payment = ""
        self.coupon = ""
        self.ride_confirmed = False
        self.ride_cancelled = False
        self.screen = "form"
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
        self.screen = str(extras.get("start_screen", "form"))
        self._touch_state()

    def reset_app(self, episode_id: str | None = None, extras: dict[str, str | int | bool] | None = None) -> None:
        self.clear_app_data()
        self.launch_app(episode_id=episode_id, extras=extras)

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
        elif resource_name == "ride_option_mini":
            self.selected_ride = "Mini"
            self.screen = "ride_options"
        elif resource_name == "ride_option_sedan":
            self.selected_ride = "Sedan"
            self.screen = "ride_options"
        elif resource_name == "ride_option_premium":
            self.selected_ride = "Premium"
            self.screen = "ride_options"
        elif resource_name == "apply_coupon_button":
            self.focus = "coupon_input"
            self.screen = "coupon"
        elif resource_name == "coupon_apply_button":
            self.screen = "coupon"
        elif resource_name == "payment_cash":
            self.payment = "cash"
            self.screen = "payment"
        elif resource_name == "payment_upi":
            self.payment = "upi"
            self.screen = "payment"
        elif resource_name == "confirm_ride_button":
            self.ride_confirmed = bool(self.ride_pickup and self.ride_drop and self.selected_ride)
            self.ride_cancelled = False
            self.screen = "driver_assigned" if self.ride_confirmed else "ride_validation_error"
        elif resource_name == "cancel_ride_button":
            self.ride_cancelled = True
            self.ride_confirmed = False
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
            self.ride_pickup = text
        elif resource_name == "drop_input":
            self.ride_drop = text
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
            "pickup_input": self.ride_pickup,
            "drop_input": self.ride_drop,
            "location_suggestion_1": "Use suggestion 1",
            "location_suggestion_2": "Use suggestion 2",
            "ride_option_mini": "Mini",
            "ride_option_sedan": "Sedan",
            "ride_option_premium": "Premium",
            "cheapest_badge": "Cheapest: Mini",
            "apply_coupon_button": "Apply Coupon",
            "coupon_input": self.coupon,
            "coupon_apply_button": "Save Coupon",
            "payment_cash": "Cash",
            "payment_upi": "UPI",
            "confirm_ride_button": "Confirm Ride",
            "cancel_ride_button": "Cancel Ride",
            "final_status_text": self.ride_status_text(),
            "debug_state_text": self.debug_state_text,
        }
        return [
            {
                "id": name,
                "resource_id": f"{self.task.package}:id/{name}",
                "text": values.get(name, ""),
                "focused": self.focus == name,
                "bounds": [0, 0, 10, 10],
                "center": [5, 5],
                "class_name": "android.widget.EditText" if name.endswith("_input") else "android.widget.TextView",
                "clickable": not name.endswith("_text"),
            }
            for name in resource_names
        ]

    def read_shared_prefs(self) -> str:
        if not (self.episode_id or self.query or self.name_text or self.email or self.submitted):
            return ""
        submitted = "true" if self.submitted else "false"
        ride_confirmed = "true" if self.ride_confirmed else "false"
        ride_cancelled = "true" if self.ride_cancelled else "false"
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\" ?>\n"
            "<map>\n"
            f"    <string name=\"episode_id\">{self.episode_id}</string>\n"
            f"    <boolean name=\"submitted\" value=\"{submitted}\" />\n"
            f"    <string name=\"query\">{self.query}</string>\n"
            f"    <string name=\"name\">{self.name_text}</string>\n"
            f"    <string name=\"email\">{self.email}</string>\n"
            f"    <string name=\"ride_pickup\">{self.ride_pickup}</string>\n"
            f"    <string name=\"ride_drop\">{self.ride_drop}</string>\n"
            f"    <string name=\"selected_ride\">{self.selected_ride}</string>\n"
            f"    <string name=\"payment\">{self.payment}</string>\n"
            f"    <string name=\"coupon\">{self.coupon}</string>\n"
            f"    <boolean name=\"ride_confirmed\" value=\"{ride_confirmed}\" />\n"
            f"    <boolean name=\"ride_cancelled\" value=\"{ride_cancelled}\" />\n"
            f"    <string name=\"screen\">{self.screen}</string>\n"
            f"    <long name=\"updated_at_ms\" value=\"{self.updated_at_ms}\" />\n"
            f"    <int name=\"seed\" value=\"{self.seed}\" />\n"
            "</map>\n"
        )

    def device_info(self) -> dict[str, str]:
        return {
            "backend": "adb",
            "serial": "mock-serial",
            "api_level": "test",
            "build_fingerprint": "mock/fingerprint",
            "screen_size": "Physical size: 1080x1920",
            "screen_density": "Physical density: 420",
            "locale": "en-US",
            "timezone": "UTC",
            "package": self.task.package,
        }

    def status_text(self) -> str:
        if self.submitted:
            return f"Submitted: {self.name_text} <{self.email}>"
        if self.screen == "validation_error":
            return "Status: missing fields"
        return "Status: waiting"

    def ride_status_text(self) -> str:
        if self.ride_cancelled:
            return "Ride cancelled"
        if self.ride_confirmed:
            return f"Driver assigned: {self.selected_ride}"
        if self.screen == "ride_validation_error":
            return "Ride status: missing fields"
        if self.selected_ride:
            return f"Ride selected: {self.selected_ride}"
        return "Ride status: waiting"

    def _touch_state(self) -> None:
        self.updated_at_ms = int(time.time() * 1000)
        self.debug_state_text = json.dumps(
            {
                "coupon": self.coupon,
                "email": self.email,
                "episode_id": self.episode_id,
                "name": self.name_text,
                "payment": self.payment,
                "query": self.query,
                "ride_cancelled": self.ride_cancelled,
                "ride_confirmed": self.ride_confirmed,
                "ride_drop": self.ride_drop,
                "ride_pickup": self.ride_pickup,
                "screen": self.screen,
                "seed": self.seed,
                "selected_ride": self.selected_ride,
                "submitted": self.submitted,
                "updated_at_ms": self.updated_at_ms,
            },
            sort_keys=True,
        )
