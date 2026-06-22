"""Throughput and scaling benchmark helpers."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from statistics import mean
from typing import Any

from android_adk_rl_env.proof_benchmark import run_proof_benchmark


def run_throughput_benchmark(
    *,
    pool_sizes: list[int],
    attempts_per_instance: int,
    pass_k: list[int],
    output_dir: str,
    tasks_dir: str = "tasks",
    max_steps: int = 12,
    policy: str = "scripted",
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    baseline_rollouts_per_second: float | None = None
    for pool_size in pool_sizes:
        started = time.perf_counter()
        summary = run_proof_benchmark(
            backend="adb",
            policy=policy,
            attempts_per_instance=attempts_per_instance,
            pass_k=pass_k,
            max_steps=max_steps,
            output_dir=str(root / f"pool_{pool_size}"),
            pool_size=pool_size,
            task_specs_dir=tasks_dir,
        )
        elapsed = max(0.001, time.perf_counter() - started)
        task_result_path = Path(summary["output_dir"]) / "task_results.jsonl"
        rows = _load_jsonl(task_result_path)
        total_attempts = len(rows)
        total_steps = sum(int(row.get("steps", 0) or 0) for row in rows)
        reset_durations = [
            float((row.get("reset_metadata") or {}).get("duration_seconds", 0.0) or 0.0)
            for row in rows
            if row.get("reset_metadata") is not None
        ]
        reset_by_mode: dict[str, list[float]] = {}
        for row in rows:
            meta = row.get("reset_metadata") or {}
            mode = str(meta.get("applied_mode", "unknown"))
            duration = float(meta.get("duration_seconds", 0.0) or 0.0)
            reset_by_mode.setdefault(mode, []).append(duration)

        rollouts_per_second = total_attempts / elapsed
        env_steps_per_second = total_steps / elapsed if total_steps else 0.0
        if pool_size == 1:
            baseline_rollouts_per_second = rollouts_per_second
        scaling_efficiency = None
        if baseline_rollouts_per_second and baseline_rollouts_per_second > 0:
            scaling_efficiency = rollouts_per_second / (baseline_rollouts_per_second * pool_size)

        result = {
            "pool_size": pool_size,
            "elapsed_seconds": elapsed,
            "total_attempts": total_attempts,
            "total_steps": total_steps,
            "rollouts_per_second": rollouts_per_second,
            "env_steps_per_second": env_steps_per_second,
            "scaling_efficiency": scaling_efficiency,
            "avg_reset_duration_seconds": mean(reset_durations) if reset_durations else 0.0,
            "reset_latency_by_mode": {
                mode: {
                    "count": len(values),
                    "mean_seconds": mean(values) if values else 0.0,
                    "min_seconds": min(values) if values else 0.0,
                    "max_seconds": max(values) if values else 0.0,
                }
                for mode, values in reset_by_mode.items()
            },
            "benchmark_summary_path": str(Path(summary["output_dir"]) / "summary.json"),
            "task_results_path": str(task_result_path),
            "pass_at_k": summary.get("pass_at_k", {}),
            "reward_report_path": str(Path(summary["output_dir"]) / "reward_report.json"),
        }
        results.append(result)

    payload = {
        "pool_sizes": pool_sizes,
        "attempts_per_instance": attempts_per_instance,
        "policy": policy,
        "tasks_dir": tasks_dir,
        "max_steps": max_steps,
        "results": results,
    }
    (root / "throughput_summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-sizes", nargs="+", type=int, default=[1, 2, 4, 8])
    parser.add_argument("--attempts-per-instance", type=int, default=int(os.environ.get("BENCHMARK_SAMPLES_PER_TASK", "10")))
    parser.add_argument("--pass-k", nargs="+", type=int, default=[1, 2, 3, 5, 10])
    parser.add_argument("--output", default="artifacts/throughput")
    parser.add_argument("--tasks-dir", default="tasks")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--policy", default="scripted", choices=["scripted", "openai", "random"])
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_throughput_benchmark(
        pool_sizes=args.pool_sizes,
        attempts_per_instance=args.attempts_per_instance,
        pass_k=args.pass_k,
        output_dir=args.output,
        tasks_dir=args.tasks_dir,
        max_steps=args.max_steps,
        policy=args.policy,
    )
    print(json.dumps(summary, indent=None if args.compact else 2, sort_keys=True))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
