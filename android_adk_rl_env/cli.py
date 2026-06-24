"""Unified mobile RL CLI for eval and benchmark workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.eval_runner import resolve_adb_serial, run_device_healthcheck, run_task_spec
from android_adk_rl_env.proof_benchmark import run_proof_benchmark
from android_adk_rl_env.task_specs import AppSpec, EvalTaskSpec, RewardSpec, SuccessSpec, load_task_spec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser("eval", help="Run one task spec or ad-hoc task.")
    eval_parser.add_argument("--task", help="YAML task spec path.")
    eval_parser.add_argument("--apk", help="APK path for ad-hoc eval.")
    eval_parser.add_argument("--package", help="Android package for ad-hoc eval.")
    eval_parser.add_argument("--goal", help="Goal text for ad-hoc eval.")
    eval_parser.add_argument("--success-check", help='Ad-hoc success expression, e.g. "prefs.submitted == true".')
    eval_parser.add_argument("--task-type", default="dummy_form", help="Runnable task type for ad-hoc eval.")
    eval_parser.add_argument("--policy", default="scripted", choices=["scripted", "openai", "random"])
    eval_parser.add_argument("--backend", default=os.environ.get("ROLLOUT_BACKEND", "adb"), choices=["adb"])
    eval_parser.add_argument("--max-steps", type=int, default=12)
    eval_parser.add_argument("--compact", action="store_true")
    eval_parser.add_argument("--no-install-apk", action="store_true")
    eval_parser.add_argument("--no-healthcheck", action="store_true")

    health_parser = subparsers.add_parser("health", help="Run ADB/device health checks.")
    health_parser.add_argument("--package", default="com.primeintellect.dummyrl")
    health_parser.add_argument("--compact", action="store_true")

    benchmark_parser = subparsers.add_parser("benchmark", help="Run benchmark task specs.")
    benchmark_parser.add_argument("--tasks-dir", default="tasks")
    benchmark_parser.add_argument("--policy", default="scripted", choices=["scripted", "openai", "random"])
    benchmark_parser.add_argument("--backend", default="adb", choices=["adb", "android_world"])
    benchmark_parser.add_argument(
        "--samples-per-task",
        type=int,
        default=int(os.environ.get("BENCHMARK_SAMPLES_PER_TASK", "10")),
    )
    benchmark_parser.add_argument("--max-steps", type=int, default=12)
    benchmark_parser.add_argument("--pass-k", nargs="+", type=int, default=[1, 2, 3, 5, 10])
    benchmark_parser.add_argument("--bootstrap-samples", type=int, default=0)
    benchmark_parser.add_argument("--bootstrap-seed", type=int, default=17230)
    benchmark_parser.add_argument("--output", default="artifacts/benchmarks")
    benchmark_parser.add_argument("--pool-size", type=int, default=int(os.environ.get("POOL_SIZE", "1")))
    benchmark_parser.add_argument("--enable-calibration", action="store_true")
    benchmark_parser.add_argument("--compact", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "eval":
        payload, exit_code = _run_eval_command(args)
    elif args.command == "health":
        payload, exit_code = _run_health_command(args)
    else:
        payload, exit_code = _run_benchmark_command(args)

    indent = None if getattr(args, "compact", False) else 2
    print(json.dumps(payload, indent=indent, sort_keys=True))
    raise SystemExit(exit_code)


def _run_eval_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        spec = load_task_spec(args.task) if args.task else _build_adhoc_spec(args)
        result = run_task_spec(
            spec,
            policy=args.policy,
            backend=args.backend,
            install_apk=not args.no_install_apk,
            healthcheck=not args.no_healthcheck,
            max_steps=args.max_steps,
        )
        return (
            {
                "harness_success": True,
                "task_success": bool(result["task_success"]),
                "exit_code": 0,
                "result": result,
            },
            0,
        )
    except Exception as exc:  # noqa: BLE001
        return (
            {
                "harness_success": False,
                "task_success": False,
                "exit_code": 2,
                "error": f"{type(exc).__name__}: {exc}",
            },
            2,
        )


def _run_benchmark_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        summary = run_proof_benchmark(
            backend=args.backend,
            policy=args.policy,
            attempts_per_instance=args.samples_per_task,
            pass_k=args.pass_k,
            max_steps=args.max_steps,
            output_dir=args.output,
            bootstrap_samples=args.bootstrap_samples,
            bootstrap_seed=args.bootstrap_seed,
            pool_size=args.pool_size,
            task_specs_dir=args.tasks_dir,
            enable_calibration=args.enable_calibration,
        )
        return summary, 0
    except Exception as exc:  # noqa: BLE001
        return {"harness_success": False, "error": f"{type(exc).__name__}: {exc}"}, 2


def _run_health_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        device = AdbDevice(
            adb_path=os.environ.get("ADB_PATH", "adb"),
            package=args.package,
            serial=os.environ.get("ADB_SERIAL") or resolve_adb_serial(os.environ.get("ADB_PATH", "adb")),
        )
        return {"harness_success": True, "healthcheck": run_device_healthcheck(device, package=args.package)}, 0
    except Exception as exc:  # noqa: BLE001
        return {"harness_success": False, "error": f"{type(exc).__name__}: {exc}"}, 2


def _build_adhoc_spec(args: argparse.Namespace) -> EvalTaskSpec:
    if not args.package or not args.goal or not args.success_check:
        raise ValueError("--task or the trio --package/--goal/--success-check is required")
    task_id = Path(args.apk or args.package).stem.replace(".", "_")
    return EvalTaskSpec(
        task_id=task_id,
        app=AppSpec(package=args.package, apk_path=args.apk),
        setup={},
        goal=args.goal,
        max_steps=args.max_steps,
        success=SuccessSpec(type="expression", check=args.success_check, threshold=1.0),
        reward=RewardSpec(mode="binary"),
        task_type=args.task_type,
        source_path=None,
    )


if __name__ == "__main__":
    main()
