"""ADB-backed device controls for the dummy Android APK."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UiNode:
    resource_id: str
    text: str
    bounds: tuple[int, int, int, int]
    focused: bool = False

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)


class AdbDevice:
    """Small ADB/UIAutomator controller used by the APK-backed task."""

    def __init__(
        self,
        adb_path: str = "adb",
        package: str = "com.primeintellect.dummyrl",
        serial: str | None = None,
    ) -> None:
        self.adb_path = adb_path
        self.package = package
        self.serial = serial

    @property
    def name(self) -> str:
        return "adb"

    def adb(self, *args: str, check: bool = True, timeout_s: int | None = None) -> subprocess.CompletedProcess[str]:
        command = [self.adb_path]
        if self.serial:
            command.extend(["-s", self.serial])
        command.extend(args)
        effective_timeout = int(timeout_s or os.environ.get("ADB_CMD_TIMEOUT_S", "60"))
        return subprocess.run(
            command,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=effective_timeout,
        )

    def connect(self) -> None:
        self.adb("start-server")
        if self.serial and ":" in self.serial:
            self.adb("connect", self.serial, check=False)

    def wait_for_ready(self, timeout_s: int = 180) -> None:
        self.connect()
        self.adb("wait-for-device")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            booted = self.adb("shell", "getprop", "sys.boot_completed", check=False).stdout.strip()
            if booted == "1":
                return
            time.sleep(1.0)
        raise RuntimeError("timed out waiting for Android boot to complete")

    def wait_for_device(self) -> None:
        self.wait_for_ready()

    def install_apk(self, apk_path: str) -> None:
        self.wait_for_ready()
        self.adb("install", "-r", apk_path)

    def force_stop(self) -> None:
        self.adb("shell", "am", "force-stop", self.package, check=False)

    def clear_app_data(self) -> None:
        self.adb("shell", "pm", "clear", self.package)

    def launch_app(self, episode_id: str | None = None, extras: dict[str, str | int | bool] | None = None) -> None:
        command = [
            "shell",
            "am",
            "start",
            "-W",
            "-S",
            "-n",
            f"{self.package}/.MainActivity",
        ]
        if episode_id:
            command.extend(["--es", "episode_id", episode_id])
        for key, value in (extras or {}).items():
            if key == "episode_id" and episode_id:
                continue
            if isinstance(value, bool):
                command.extend(["--ez", key, "true" if value else "false"])
            elif isinstance(value, int):
                command.extend(["--ei", key, str(value)])
            else:
                command.extend(["--es", key, str(value)])
        self.adb(*command, timeout_s=60)
        time.sleep(1.0)

    def reset_app(self, episode_id: str | None = None, extras: dict[str, str | int | bool] | None = None) -> None:
        self.wait_for_ready()
        self.force_stop()
        self.clear_app_data()
        self.launch_app(episode_id=episode_id, extras=extras)
        self.wait_for_ui_ready()

    def is_emulator(self) -> bool:
        if self.serial and self.serial.startswith("emulator-"):
            return True
        result = self.adb("shell", "getprop", "ro.kernel.qemu", check=False)
        return result.stdout.strip() == "1"

    def snapshot_exists(self, snapshot_name: str) -> bool:
        if not self.is_emulator():
            return False
        result = self.adb("emu", "avd", "snapshot", "list", check=False)
        lines = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return snapshot_name in lines

    def save_snapshot(self, snapshot_name: str) -> None:
        if not self.is_emulator():
            raise RuntimeError("snapshot save requires an emulator-backed device")
        self.adb("emu", "avd", "snapshot", "save", snapshot_name)
        time.sleep(1.0)

    def restore_snapshot(self, snapshot_name: str) -> None:
        if not self.is_emulator():
            raise RuntimeError("snapshot restore requires an emulator-backed device")
        self.adb("emu", "avd", "snapshot", "load", snapshot_name)
        self.wait_for_ready()

    def wait_for_ui_ready(self) -> None:
        deadline = time.time() + 10.0
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                if self.dismiss_blocking_system_dialog():
                    time.sleep(0.5)
                    continue
                focus_package = self.current_focus_package()
                if focus_package is not None and focus_package != self.package:
                    time.sleep(0.5)
                    continue
                self.find_resource("status_text")
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.5)
        raise RuntimeError(f"UI did not become ready: {last_error}")

    def current_focus_package(self) -> str | None:
        result = self.adb("shell", "dumpsys", "window", "windows", check=False)
        text = result.stdout
        for line in text.splitlines():
            if "mCurrentFocus" not in line and "mFocusedApp" not in line:
                continue
            marker = " u0 "
            if marker in line:
                fragment = line.split(marker, 1)[1]
                package_activity = fragment.split()[0]
                if "/" in package_activity:
                    return package_activity.split("/", 1)[0]
        return None

    def click_resource(self, resource_name: str) -> None:
        node = self.find_resource(resource_name)
        x, y = node.center
        self.adb("shell", "input", "tap", str(x), str(y))
        time.sleep(0.3)

    def input_resource(self, resource_name: str, text: str) -> None:
        self.focus_resource(resource_name)
        self.adb("shell", "input", "keyevent", "KEYCODE_CTRL_A", check=False)
        self.adb("shell", "input", "text", self._escape_input_text(text))
        time.sleep(0.3)

    def focus_resource(self, resource_name: str) -> None:
        for _ in range(3):
            self.click_resource(resource_name)
            if self.find_resource(resource_name).focused:
                return
            time.sleep(0.3)
        node = self.find_resource(resource_name)
        if not node.focused:
            raise RuntimeError(f"resource did not focus: {resource_name}")

    def press_back(self) -> None:
        self.adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.3)

    def press_home(self) -> None:
        self.adb("shell", "input", "keyevent", "KEYCODE_HOME")
        time.sleep(0.3)

    def tap_coordinates(self, x: int, y: int) -> None:
        self.adb("shell", "input", "tap", str(x), str(y))
        time.sleep(0.3)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
        time.sleep(0.3)

    def dump_ui(self) -> str:
        last_error: Exception | None = None
        for _ in range(3):
            try:
                result = self.adb("shell", "uiautomator", "dump", "/sdcard/window.xml", check=False, timeout_s=30)
                if result.returncode not in {0, 137}:
                    raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "uiautomator dump failed")
                xml_text = self.adb("exec-out", "cat", "/sdcard/window.xml", timeout_s=30).stdout
                if xml_text.strip():
                    return xml_text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            time.sleep(0.5)
        raise RuntimeError(f"failed to dump ui: {last_error}")

    def find_resource(self, resource_name: str) -> UiNode:
        full_id = f"{self.package}:id/{resource_name}"
        xml_text = self.dump_ui()
        root = ET.fromstring(xml_text)
        for elem in root.iter("node"):
            if elem.attrib.get("resource-id") == full_id:
                return UiNode(
                    resource_id=full_id,
                    text=elem.attrib.get("text", ""),
                    bounds=self._parse_bounds(elem.attrib["bounds"]),
                    focused=elem.attrib.get("focused") == "true",
                )
        raise LookupError(f"resource not found: {full_id}")

    def dismiss_blocking_system_dialog(self) -> bool:
        for resource_id in ("android:id/aerr_close", "android:id/button1"):
            try:
                node = self.find_any_resource(resource_id)
            except LookupError:
                continue
            x, y = node.center
            self.adb("shell", "input", "tap", str(x), str(y))
            time.sleep(0.5)
            return True
        return False

    def find_any_resource(self, full_resource_id: str) -> UiNode:
        xml_text = self.dump_ui()
        root = ET.fromstring(xml_text)
        for elem in root.iter("node"):
            if elem.attrib.get("resource-id") != full_resource_id:
                continue
            return UiNode(
                resource_id=full_resource_id,
                text=elem.attrib.get("text", ""),
                bounds=self._parse_bounds(elem.attrib["bounds"]),
                focused=elem.attrib.get("focused") == "true",
            )
        raise LookupError(f"resource not found: {full_resource_id}")

    def _resource_nodes_from_xml(self, xml_text: str, resource_names: tuple[str, ...]) -> list[dict[str, object]]:
        wanted = {f"{self.package}:id/{name}": name for name in resource_names}
        root = ET.fromstring(xml_text)
        nodes: list[dict[str, object]] = []
        for index, elem in enumerate(root.iter("node")):
            full_id = elem.attrib.get("resource-id", "")
            if full_id not in wanted:
                continue
            node = UiNode(
                resource_id=full_id,
                text=elem.attrib.get("text", ""),
                bounds=self._parse_bounds(elem.attrib["bounds"]),
                focused=elem.attrib.get("focused") == "true",
            )
            nodes.append(
                {
                    "id": wanted[full_id],
                    "element_index": index,
                    "resource_id": node.resource_id,
                    "text": node.text,
                    "bounds": list(node.bounds),
                    "center": list(node.center),
                    "focused": node.focused,
                    "class_name": elem.attrib.get("class", ""),
                    "clickable": elem.attrib.get("clickable") == "true",
                }
            )
        return nodes

    def dump_resource_nodes(self, resource_names: tuple[str, ...]) -> list[dict[str, object]]:
        xml_text = self.dump_ui()
        return self._resource_nodes_from_xml(xml_text, resource_names)

    def read_shared_prefs(self) -> str:
        try:
            result = self.adb(
                "shell",
                "run-as",
                self.package,
                "cat",
                "shared_prefs/dummy_state.xml",
                check=False,
            )
            if result.stdout.strip():
                return result.stdout
        except subprocess.TimeoutExpired:
            pass
        return self._debug_state_as_prefs()

    def device_info(self) -> dict[str, str]:
        return {
            "backend": self.name,
            "serial": self.serial or "",
            "api_level": self.adb("shell", "getprop", "ro.build.version.sdk", check=False).stdout.strip(),
            "build_fingerprint": self.adb("shell", "getprop", "ro.build.fingerprint", check=False).stdout.strip(),
            "screen_size": self.adb("shell", "wm", "size", check=False).stdout.strip(),
            "screen_density": self.adb("shell", "wm", "density", check=False).stdout.strip(),
            "locale": self.adb("shell", "getprop", "persist.sys.locale", check=False).stdout.strip(),
            "timezone": self.adb("shell", "getprop", "persist.sys.timezone", check=False).stdout.strip(),
            "package": self.package,
        }

    def clone_with(self, **overrides: Any) -> "AdbDevice":
        return AdbDevice(
            adb_path=str(overrides.get("adb_path", self.adb_path)),
            package=str(overrides.get("package", self.package)),
            serial=overrides.get("serial", self.serial),
        )

    def _parse_bounds(self, raw: str) -> tuple[int, int, int, int]:
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", raw)
        if not match:
            raise ValueError(f"invalid bounds: {raw}")
        values = tuple(int(group) for group in match.groups())
        return values  # type: ignore[return-value]

    def _escape_input_text(self, text: str) -> str:
        return (
            text.replace("%", "%25")
            .replace(" ", "%s")
            .replace("&", r"\&")
            .replace("<", r"\<")
            .replace(">", r"\>")
        )

    def _debug_state_as_prefs(self) -> str:
        try:
            node = self.find_resource("debug_state_text")
        except Exception:
            return ""
        raw = (node.text or "").strip()
        if not raw:
            return ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return ""
        lines = ["<map>"]
        for key, value in data.items():
            if isinstance(value, bool):
                lines.append(f'<boolean name="{key}" value="{"true" if value else "false"}" />')
            elif isinstance(value, int):
                lines.append(f'<long name="{key}" value="{value}" />')
            else:
                lines.append(f'<string name="{key}">{value}</string>')
        lines.append("</map>")
        return "\n".join(lines)
