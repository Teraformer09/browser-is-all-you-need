"""Train a local RL-only policy on the dummy APK environment."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.local_rl import (
    CandidateActionSpace,
    RlTrainConfig,
    evaluate_policy,
    make_env_factory,
    save_checkpoint,
    save_episodes,
    summarize_episodes,
    train_policy,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--eval-episodes", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=0.15)
    parser.add_argument("--gamma", type=float, default=0.95)
    parser.add_argument("--entropy-coef", type=float, default=0.01)
    parser.add_argument("--success-bonus", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--checkpoint", default="artifacts/rl/dummy_apk_policy.json")
    parser.add_argument("--train-output", default="artifacts/rl/dummy_apk_rl_train.jsonl")
    parser.add_argument("--eval-output", default="artifacts/rl/dummy_apk_rl_eval.jsonl")
    parser.add_argument("--install-apk", action="store_true")
    parser.add_argument("--sparse-reward", action="store_true")
    parser.add_argument("--no-distractors", action="store_true")
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.install_apk:
        root = Path(__file__).resolve().parents[1]
        subprocess.run([str(root / "scripts" / "build_dummy_apk.sh")], check=True)
        subprocess.run([str(root / "scripts" / "install_dummy_apk.sh")], check=True)

    task = DummyApkFormSearchTask(max_steps=args.max_steps)
    config = RlTrainConfig(
        episodes=args.episodes,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        gamma=args.gamma,
        entropy_coef=args.entropy_coef,
        success_bonus=args.success_bonus,
        seed=args.seed,
    )
    env_factory = make_env_factory(task=task, max_steps=args.max_steps, shaped_rewards=not args.sparse_reward)
    action_space = CandidateActionSpace(task=task, include_distractors=not args.no_distractors)
    policy, train_episodes = train_policy(env_factory=env_factory, config=config, action_space=action_space)
    eval_episodes = evaluate_policy(env_factory=env_factory, policy=policy, episodes=args.eval_episodes)

    save_checkpoint(args.checkpoint, policy, config)
    save_episodes(args.train_output, train_episodes)
    save_episodes(args.eval_output, eval_episodes)

    summary = {
        "mode": "rl_only",
        "checkpoint": args.checkpoint,
        "train_output": args.train_output,
        "eval_output": args.eval_output,
        "train": summarize_episodes(train_episodes),
        "eval": summarize_episodes(eval_episodes),
    }
    print(json.dumps(summary, indent=None if args.compact else 2, sort_keys=True))


if __name__ == "__main__":
    main()
