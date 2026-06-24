"""Benchmark runner for spec-driven Android APK evaluation."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from android_adk_rl_env.benchmarking.pass_at_k import compute_pass_at_k, summarize_pass_at_k
from android_adk_rl_env.benchmarking.reward_stats import check_reward_calibration, summarize_reward_distributions
from android_adk_rl_env.device_pool import DevicePool
from android_adk_rl_env.eval_runner import run_task_spec
from android_adk_rl_env.task_specs import EvalTaskSpec, load_task_specs_from_dir


def run_proof_benchmark(
    backend: str = "adb",
    policy: str = "scripted",
    attempts_per_instance: int = 10,
    pass_k: list[int] | None = None,
    max_steps: int = 12,
    output_dir: str = "artifacts/benchmarks",
    bootstrap_samples: int = 0,
    bootstrap_seed: int = 17230,
    install_check: bool = True,
    pool_size: int = 1,
    task_specs_dir: str = "tasks",
    enable_calibration: bool = False,
) -> dict[str, Any]:
    del install_check
    pass_k = sorted(set(int(value) for value in (pass_k or [1, 2, 3, 5, 10]) if int(value) > 0))
    if not pass_k:
        raise ValueError("at least one positive k value is required")
    if policy == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --policy openai")

    specs = [spec for spec in load_task_specs_from_dir(task_specs_dir) if "benchmark" in spec.tags or not spec.tags]
    if not specs:
        raise RuntimeError(f"no benchmark task specs found in {task_specs_dir}")

    started = _now_iso()
    run_root = Path(output_dir)
    run_root.mkdir(parents=True, exist_ok=True)
    run_dir = run_root / _run_id()
    run_dir.mkdir(parents=True, exist_ok=True)

    pool = DevicePool.from_environment(pool_size=pool_size)
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool.pool_size) as executor:
        futures = []
        for spec in specs:
            for attempt in range(attempts_per_instance):
                futures.append(executor.submit(_run_attempt, spec, attempt, policy, backend, max_steps, pool))
        for future in concurrent.futures.as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: (str(row.get("benchmark_family", "")), int(row.get("instance_attempt", 0))))

    successes_by_task = _group_bool_metric(rows, "task_id", "task_success")
    rewards_by_task = _group_float_metric(rows, "task_id", "reward")
    thresholds = {spec.task_id: spec.success.threshold for spec in specs}
    pass_rates = compute_pass_at_k(successes_by_task, pass_k)
    pass_confidence = summarize_pass_at_k(
        successes_by_task,
        pass_k,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    reward_report = summarize_reward_distributions(
        rewards_by_task,
        thresholds=thresholds,
        k_values=pass_k,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )

    calibration: dict[str, Any] = {}
    if enable_calibration and policy == "scripted":
        calibration_rows = _run_calibration(specs, attempts_per_instance, backend, max_steps, pool)
        random_rewards = _group_float_metric(calibration_rows, "task_id", "reward")
        calibration = check_reward_calibration(
            good_policy_rewards=rewards_by_task,
            bad_policy_rewards=random_rewards,
            thresholds=thresholds,
            bootstrap_samples=max(bootstrap_samples, 200),
            bootstrap_seed=bootstrap_seed,
        )

    summary = {
        "run_id": run_dir.name,
        "backend": backend,
        "policy": policy,
        "samples_per_task": attempts_per_instance,
        "task_count": len(specs),
        "total_attempts": len(rows),
        "pass_k_values": pass_k,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "pool_size": pool_size,
        "task_specs_dir": task_specs_dir,
        "output_dir": str(run_dir),
        "started_at": started,
        "ended_at": _now_iso(),
        "exact_success_rate": mean(1.0 if row.get("task_success") else 0.0 for row in rows) if rows else 0.0,
        "avg_reward": mean(float(row.get("reward", 0.0) or 0.0) for row in rows) if rows else 0.0,
        "avg_steps": mean(int(row.get("steps", 0) or 0) for row in rows) if rows else 0.0,
        "pass_at_k": pass_rates,
        "pass_at_k_ci": pass_confidence,
        "reward_report": reward_report,
        "reward_calibration": calibration,
    }

    _write_json(run_dir / "summary.json", summary)
    _write_jsonl(run_dir / "task_results.jsonl", rows)
    _write_json(run_dir / "pass_at_k.json", {"pass_at_k": pass_rates, "confidence_intervals": pass_confidence})
    _write_json(run_dir / "reward_report.json", reward_report)
    if calibration:
        _write_json(run_dir / "reward_calibration.json", calibration)
    _write_json(
        run_dir / "config.json",
        {
            "backend": backend,
            "policy": policy,
            "samples_per_task": attempts_per_instance,
            "pass_k": pass_k,
            "max_steps": max_steps,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_seed": bootstrap_seed,
            "pool_size": pool_size,
            "task_specs_dir": task_specs_dir,
            "enable_calibration": enable_calibration,
        },
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default="scripted", choices=["scripted", "openai", "random"])
    parser.add_argument("--backend", default="adb", choices=["adb", "android_world"])
    parser.add_argument(
        "--attempts-per-instance",
        type=int,
        default=int(os.environ.get("BENCHMARK_SAMPLES_PER_TASK", "10")),
    )
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--pass-k", nargs="+", type=int, default=[1, 2, 3, 5, 10])
    parser.add_argument("--bootstrap-samples", type=int, default=0)
    parser.add_argument("--bootstrap-seed", type=int, default=17230)
    parser.add_argument("--output", default="artifacts/benchmarks")
    parser.add_argument("--pool-size", type=int, default=int(os.environ.get("POOL_SIZE", "1")))
    parser.add_argument("--tasks-dir", default="tasks")
    parser.add_argument("--enable-calibration", action="store_true")
    parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = run_proof_benchmark(
        backend=args.backend,
        policy=args.policy,
        attempts_per_instance=args.attempts_per_instance,
        pass_k=args.pass_k,
        max_steps=args.max_steps,
        output_dir=args.output,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
        pool_size=args.pool_size,
        task_specs_dir=args.tasks_dir,
        enable_calibration=args.enable_calibration,
    )
    if args.compact:
        print(json.dumps(summary, sort_keys=True))
        return
    print("Proof benchmark completed")
    print(f"Run ID: {summary['run_id']}")
    print(f"Backend: {summary['backend']}")
    print(f"Policy: {summary['policy']}")
    print(f"Tasks: {summary['task_count']}")
    print(f"Total attempts: {summary['total_attempts']}")
    print(f"Pass@1: {summary['pass_at_k'].get('pass@1', 0.0):.3f}")
    print(f"Pass@5: {summary['pass_at_k'].get('pass@5', 0.0):.3f}")
    print(f"Avg reward: {summary['avg_reward']:.3f}")
    print(f"Artifacts: {summary['output_dir']}")


def _run_attempt(
    spec: EvalTaskSpec,
    attempt: int,
    policy: str,
    backend: str,
    max_steps: int,
    pool: DevicePool,
) -> dict[str, Any]:
    wall_started = _now_iso()
    with pool.lease() as device_spec:
        try:
            row = run_task_spec(
                spec,
                policy=policy,
                backend=backend,
                serial=device_spec.serial,
                attempt=attempt,
                install_apk=attempt == 0,
                healthcheck=attempt == 0,
                max_steps=max_steps,
            )
        except Exception as exc:  # noqa: BLE001
            row = {
                "task_id": spec.task_id,
                "benchmark_family": spec.family_id,
                "task_type": spec.task_type,
                "policy": policy,
                "backend": backend,
                "reward": 0.0,
                "final_reward": 0.0,
                "success_score": 0.0,
                "success_threshold": spec.success.threshold,
                "task_success": False,
                "exact_success": False,
                "steps": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
    wall_ended = _now_iso()
    row["instance_attempt"] = attempt + 1
    row["attempt_id"] = f"{spec.task_id}_{attempt + 1:03d}"
    row["attempt_started_at"] = wall_started
    row["attempt_ended_at"] = wall_ended
    return row


def _run_calibration(
    specs: list[EvalTaskSpec],
    attempts_per_instance: int,
    backend: str,
    max_steps: int,
    pool: DevicePool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool.pool_size) as executor:
        futures = []
        for spec in specs:
            if spec.task_type != "dummy_form":
                continue
            for attempt in range(attempts_per_instance):
                futures.append(executor.submit(_run_attempt, spec, attempt, "random", backend, max_steps, pool))
        for future in concurrent.futures.as_completed(futures):
            rows.append(future.result())
    return rows


def _group_bool_metric(rows: list[dict[str, Any]], group_key: str, metric_key: str) -> dict[str, list[bool]]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        grouped[str(row[group_key])].append(bool(row.get(metric_key)))
    return grouped


def _group_float_metric(rows: list[dict[str, Any]], group_key: str, metric_key: str) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row[group_key])].append(float(row.get(metric_key, 0.0) or 0.0))
    return grouped


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
