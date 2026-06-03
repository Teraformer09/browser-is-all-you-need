"""ADB-backed device controls for the dummy Android APK."""

from __future__ import annotations

import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


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

    def __init__(self, adb_path: str = "adb", package: str = "com.primeintellect.dummyrl") -> None:
        self.adb_path = adb_path
        self.package = package

    def adb(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.adb_path, *args],
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def wait_for_device(self) -> None:
        self.adb("wait-for-device")

    def clear_app_data(self) -> None:
        self.adb("shell", "pm", "clear", self.package)

    def launch_app(self) -> None:
        self.adb(
            "shell",
            "am",
            "start",
            "-W",
            "-S",
            "-n",
            f"{self.package}/.MainActivity",
        )
        time.sleep(1.0)

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

    def dump_ui(self) -> str:
        self.adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
        return self.adb("exec-out", "cat", "/sdcard/window.xml").stdout

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


    def dump_resource_nodes(self, resource_names: tuple[str, ...]) -> list[dict[str, object]]:
        wanted = {f"{self.package}:id/{name}": name for name in resource_names}
        xml_text = self.dump_ui()
        root = ET.fromstring(xml_text)
        nodes: list[dict[str, object]] = []
        for elem in root.iter("node"):
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
                    "resource_id": node.resource_id,
                    "text": node.text,
                    "bounds": list(node.bounds),
                    "center": list(node.center),
                    "focused": node.focused,
                }
            )
        return nodes

    def read_shared_prefs(self) -> str:
        result = self.adb(
            "shell",
            "run-as",
            self.package,
            "cat",
            "shared_prefs/dummy_state.xml",
            check=False,
        )
        return result.stdout

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
