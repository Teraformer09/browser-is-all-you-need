"""Benchmark a saved local RL-only policy on the dummy APK environment."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.local_rl import (
    evaluate_policy,
    load_checkpoint,
    make_env_factory,
    save_episodes,
    summarize_episodes,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="artifacts/rl/dummy_apk_policy.json")
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--output", default="artifacts/rl/dummy_apk_rl_benchmark.jsonl")
    parser.add_argument("--install-apk", action="store_true")
    parser.add_argument("--sparse-reward", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.install_apk:
        root = Path(__file__).resolve().parents[1]
        subprocess.run([str(root / "scripts" / "build_dummy_apk.sh")], check=True)
        subprocess.run([str(root / "scripts" / "install_dummy_apk.sh")], check=True)

    task = DummyApkFormSearchTask(max_steps=args.max_steps)
    policy = load_checkpoint(args.checkpoint, seed=args.seed)
    env_factory = make_env_factory(task=task, max_steps=args.max_steps, shaped_rewards=not args.sparse_reward)
    episodes = evaluate_policy(env_factory=env_factory, policy=policy, episodes=args.episodes)
    save_episodes(args.output, episodes)
    summary = {
        "mode": "rl_only_benchmark",
        "checkpoint": args.checkpoint,
        "output": args.output,
        "metrics": summarize_episodes(episodes),
    }
    print(json.dumps(summary, indent=None if args.compact else 2, sort_keys=True))


if __name__ == "__main__":
    main()
