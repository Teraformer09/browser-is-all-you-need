#!/usr/bin/env python3
"""Build a lightweight UI graph for the dummy APK."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["adb"], default="adb")
    parser.add_argument("--output", default="artifacts/ui_graphs/dummy_apk_graph.json")
    args = parser.parse_args()

    task = DummyApkFormSearchTask()
    device = AdbDevice(package=task.package)

    device.reset_app(episode_id=task.episode_id, extras=task.launch_extras())
    home_nodes = device.dump_resource_nodes(task.resource_names)
    device.input_resource("search_input", task.query)
    device.click_resource("search_button")
    device.input_resource("name_input", task.name)
    device.input_resource("email_input", task.email)
    device.click_resource("submit_button")
    submitted_nodes = device.dump_resource_nodes(task.resource_names)

    graph = {
        "app": task.package,
        "backend": args.backend,
        "seed": task.seed,
        "screens": [
            {
                "screen_id": "home",
                "elements": [_element(node) for node in home_nodes],
                "transitions": [
                    {
                        "action": {"type": "tap_element", "element_id": "submit_button"},
                        "to_screen": "submitted",
                    }
                ],
            },
            {
                "screen_id": "submitted",
                "elements": [_element(node) for node in submitted_nodes],
                "transitions": [],
            },
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(graph, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "screens": len(graph["screens"])}, sort_keys=True))


def _element(node: dict[str, object]) -> dict[str, object]:
    return {
        "resource_id": node.get("id"),
        "text": node.get("text", ""),
        "bounds": node.get("bounds", []),
        "clickable": bool(node.get("clickable", False)),
        "input": str(node.get("id", "")).endswith("_input"),
    }


if __name__ == "__main__":
    main()
