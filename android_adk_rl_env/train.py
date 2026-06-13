"""Collect APK rollouts with scripted or OpenAI policies."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from android_adk_rl_env.apk_env import DummyApkEnv
from android_adk_rl_env.envs.mobile_task_env import make_mobile_task_env
from android_adk_rl_env.policies.openai_policy import OpenAIActionPolicy
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.rollout import run_rollouts, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="dummy_apk", choices=["dummy_apk"])
    parser.add_argument("--policy", default="scripted", choices=["scripted", "openai"])
    parser.add_argument("--backend", default="adb", choices=["adb"])
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--output", default="artifacts/rollouts/dummy_apk_rollouts.jsonl")
    parser.add_argument("--install-apk", action="store_true")
    parser.add_argument("--sparse-reward", action="store_true", help="Use final 0/1 reward instead of shaped partial reward.")
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.install_apk:
        root = Path(__file__).resolve().parents[1]
        subprocess.run([str(root / "scripts" / "build_dummy_apk.sh")], check=True)
        subprocess.run([str(root / "scripts" / "install_dummy_apk.sh")], check=True)

    task = DummyApkFormSearchTask()

    def env_factory() -> DummyApkEnv:
        return make_mobile_task_env(
            backend=args.backend,
            task=task,
            max_steps=args.max_steps,
            shaped_rewards=not args.sparse_reward,
        )

    def policy_factory() -> Any:
        if args.policy == "scripted":
            return ScriptedApkPolicy(task=task)
        return OpenAIActionPolicy(model=args.model)

    rollouts = run_rollouts(env_factory=env_factory, policy_factory=policy_factory, episodes=args.episodes)
    write_jsonl(args.output, rollouts)

    summary = {
        "task": args.task,
        "policy": args.policy,
        "backend": args.backend,
        "episodes": len(rollouts),
        "successes": sum(1 for rollout in rollouts if rollout["success"]),
        "success_rate": sum(1 for rollout in rollouts if rollout["success"]) / len(rollouts) if rollouts else 0.0,
        "output": args.output,
        "rollouts": rollouts if not args.compact else None,
    }
    if args.compact:
        del summary["rollouts"]
    print(json.dumps(summary, indent=None if args.compact else 2, sort_keys=True))


if __name__ == "__main__":
    main()
