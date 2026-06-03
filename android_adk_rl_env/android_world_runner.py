"""Run dummy APK tasks through AndroidWorld when installed.

The AndroidWorld backend uses AndroidWorld's controller, AsyncEnv, State, and
JSONAction stack. The ADB backend remains available as a compatibility fallback
for local development environments that do not have AndroidWorld installed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from android_adk_rl_env.android_world_bridge import (
    AndroidWorldNotInstalledError,
    android_world_status,
    create_native_android_world_env,
)
from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import DummyApkEnv
from android_adk_rl_env.policies.openai_policy import OpenAIActionPolicy
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.rollout import run_rollouts, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["android_world", "adb"], default="android_world")
    parser.add_argument("--policy", choices=["scripted", "openai"], default="scripted")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--output", default="artifacts/android_world/dummy_apk_rollouts.jsonl")
    parser.add_argument("--install-apk", action="store_true")
    parser.add_argument("--sparse-reward", action="store_true")
    parser.add_argument("--wait-to-stabilize", action="store_true")
    parser.add_argument("--console-port", type=int, default=5554)
    parser.add_argument("--grpc-port", type=int, default=8554)
    parser.add_argument("--adb-path", default="adb")
    parser.add_argument("--adb-serial")
    parser.add_argument("--status", action="store_true", help="Print AndroidWorld availability and exit.")
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    status = android_world_status()
    if args.status:
        print(json.dumps(status.__dict__, sort_keys=True))
        return

    if args.install_apk:
        root = Path(__file__).resolve().parents[1]
        subprocess.run([str(root / "scripts" / "build_dummy_apk.sh")], check=True)
        subprocess.run([str(root / "scripts" / "install_dummy_apk.sh")], check=True)

    task = DummyApkFormSearchTask(max_steps=args.max_steps)

    def env_factory() -> Any:
        if args.backend == "android_world":
            return create_native_android_world_env(
                console_port=args.console_port,
                adb_path=args.adb_path,
                adb_serial=args.adb_serial,
                grpc_port=args.grpc_port,
                task=task,
                max_steps=args.max_steps,
                shaped_rewards=not args.sparse_reward,
                wait_to_stabilize=args.wait_to_stabilize,
            )
        return DummyApkEnv(
            task=task,
            device=AdbDevice(adb_path=args.adb_path, package=task.package, serial=args.adb_serial),
            max_steps=args.max_steps,
            shaped_rewards=not args.sparse_reward,
        )

    def policy_factory() -> Any:
        if args.policy == "scripted":
            return ScriptedApkPolicy(task=task)
        return OpenAIActionPolicy(model=args.model)

    try:
        rollouts = run_rollouts(env_factory=env_factory, policy_factory=policy_factory, episodes=args.episodes)
    except AndroidWorldNotInstalledError as exc:
        raise SystemExit(str(exc)) from exc

    write_jsonl(args.output, rollouts)
    successes = sum(1 for rollout in rollouts if rollout.get("success"))
    summary = {
        "backend": args.backend,
        "policy": args.policy,
        "episodes": len(rollouts),
        "successes": successes,
        "success_rate": successes / len(rollouts) if rollouts else 0.0,
        "output": args.output,
        "android_world_installed": status.installed,
    }
    print(json.dumps(summary, indent=None if args.compact else 2, sort_keys=True))


if __name__ == "__main__":
    main()
