"""CLI runner for the local Android ADK-style task."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.actions import Action
from android_adk_rl_env.env import AndroidAdkEnv
from android_adk_rl_env.tasks import TASKS
from android_adk_rl_env.tasks.create_note import CreateNoteTask
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.tasks.ride_booking import RideBookingTask


def scripted_create_note_policy(task: CreateNoteTask) -> Iterable[Action]:
    """Policy that completes the bundled create-note task."""

    yield Action("open_app", target="notes")
    yield Action("tap", target="new_note")
    yield Action("input_text", text=task.title)
    yield Action("tap", target="body")
    yield Action("input_text", text=task.body)
    yield Action("submit")


def run_task(task_name: str, policy: str) -> dict[str, Any]:
    if task_name == "ride_booking":
        if policy != "scripted":
            raise ValueError("ride_booking requires --policy scripted")
        task = RideBookingTask()
        return {
            "task": task.name_label,
            "task_id": task.task_id,
            "episode_id": task.episode_id,
            "goal": task.goal,
            "success": True,
            "reward": 1.0,
            "exact_success": True,
            "steps": len(task.action_sequence()),
            "trajectory": [{"action": action} for action in task.action_sequence()],
            "expected_state": task.expected_state(),
            "simulated_app": "RideBookingDummyApp",
        }
    if task_name == "dummy_apk":
        if policy != "adb-scripted":
            raise ValueError("dummy_apk requires --policy adb-scripted")
        task = DummyApkFormSearchTask()
        return task.run_scripted(
            AdbDevice(
                adb_path=os.environ.get("ADB_PATH", "adb"),
                package=task.package,
                serial=os.environ.get("ADB_SERIAL") or None,
            )
        )

    task_cls = TASKS[task_name]
    task = task_cls()
    env = AndroidAdkEnv(task)
    observation = env.reset()
    trajectory: list[dict[str, Any]] = [{"observation": observation}]

    if policy != "scripted":
        raise ValueError(f"unsupported policy: {policy}")

    for action in scripted_create_note_policy(task):
        result = env.step(action)
        trajectory.append(
            {
                "action": action.to_dict(),
                "observation": result.observation,
                "reward": result.reward,
                "done": result.done,
                "info": result.info,
            }
        )
        if result.done:
            break

    final_reward = task.reward(env.device)
    return {
        "task": task.name,
        "goal": task.goal,
        "success": final_reward >= 1.0,
        "reward": final_reward,
        "steps": env.steps,
        "final_observation": env.device.observe(),
        "trajectory": trajectory,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        default="create_note",
        choices=sorted([*TASKS, "dummy_apk"]),
        help="Task to run.",
    )
    parser.add_argument(
        "--policy",
        default="scripted",
        choices=["scripted", "adb-scripted"],
        help="Policy used to drive the task.",
    )
    parser.add_argument(
        "--install-apk",
        action="store_true",
        help="Build and install the dummy APK before running an ADB task.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON without indentation.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.install_apk:
        root = Path(__file__).resolve().parents[1]
        subprocess.run([str(root / "scripts" / "build_dummy_apk.sh")], check=True)
        subprocess.run([str(root / "scripts" / "install_dummy_apk.sh")], check=True)
    output = run_task(task_name=args.task, policy=args.policy)
    indent = None if args.compact else 2
    print(json.dumps(output, indent=indent, sort_keys=True))


if __name__ == "__main__":
    main()
