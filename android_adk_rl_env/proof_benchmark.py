"""Proof benchmark runner for the real Android proof path.

Runs a fixed set of deterministic APK tasks repeatedly to produce
repeatability statistics such as pass@k, safe-pass@k, reliability,
and confidence intervals.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import DummyApkEnv
from android_adk_rl_env.device_pool import DevicePool, DeviceSpec
from android_adk_rl_env.policies.openai_policy import OpenAIActionPolicy
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.tasks.ride_booking import RideBookingTask
from android_adk_rl_env.training.rollout import run_rollouts


def run_proof_benchmark(
    backend: str = "adb",
    policy: str = "scripted",
    attempts_per_instance: int = 20,
    pass_k: list[int] | None = None,
    max_steps: int = 12,
    output_dir: str = "artifacts/benchmarks",
    bootstrap_samples: int = 0,
    bootstrap_seed: int = 17230,
    install_check: bool = True,
    pool_size: int = 1,
) -> dict[str, Any]:
    pass_k = pass_k or [1, 2, 5, 10]
    pass_k = sorted(set(int(value) for value in pass_k if int(value) > 0))
    if not pass_k:
        pass_k = [1]

    if backend != "adb":
        raise RuntimeError("Proof benchmark supports adb-only execution in this proof path")
    if policy == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --policy openai")

    tasks = _build_task_specs()
    started = _now_iso()
    run_root = Path(output_dir)
    run_root.mkdir(parents=True, exist_ok=True)
    run_dir = run_root / _run_id()
    run_dir.mkdir(parents=True, exist_ok=True)

    attempt_rows: list[dict[str, Any]] = []
    bootstrap_rng = random.Random(bootstrap_seed)
    pool = DevicePool.from_environment(pool_size=pool_size)
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool.pool_size) as executor:
        futures = []
        for spec in tasks:
            for attempt in range(attempts_per_instance):
                futures.append(
                    executor.submit(
                        _run_benchmark_attempt,
                        spec,
                        attempt,
                        backend,
                        policy,
                        max_steps,
                        pool,
                    )
                )
        for future in concurrent.futures.as_completed(futures):
            attempt_rows.append(future.result())
    attempt_rows.sort(key=lambda row: (str(row.get("task_family", "")), int(row.get("instance_attempt", 0))))

    task_groups = _group_by_family(attempt_rows)
    pass_at_k = _compute_pass_at_k(task_groups, pass_k, success_key="exact_success")
    safe_pass_at_k = _compute_pass_at_k(task_groups, pass_k, success_key="safe_success")
    exact_reliable = _compute_reliable(task_groups, pass_k, success_key="exact_success")
    safe_reliable = _compute_reliable(task_groups, pass_k, success_key="safe_success")

    confidence_intervals: dict[str, Any] = {}
    if bootstrap_samples > 0:
        confidence_intervals = _compute_confidence_intervals(
            task_groups=task_groups,
            pass_k=pass_k,
            success_key="exact_success",
            safe_success_key="safe_success",
            bootstrap_samples=bootstrap_samples,
            rng=bootstrap_rng,
            seed=bootstrap_seed,
        )

    metrics = _summarize_rows(
        rows=attempt_rows,
        pass_at_k=pass_at_k,
        safe_pass_at_k=safe_pass_at_k,
        exact_reliable=exact_reliable,
        safe_reliable=safe_reliable,
        pass_k=pass_k,
    )

    summary = {
        "run_id": run_dir.name,
        "backend": backend,
        "policy": policy,
        "attempts_per_instance": attempts_per_instance,
        "task_instances": len(task_groups),
        "total_attempts": len(attempt_rows),
        "pass_k_values": pass_k,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "pool_size": pool_size,
        "output_dir": str(run_dir),
        "started_at": started,
        "ended_at": _now_iso(),
        **metrics,
    }

    _write_json(run_dir / "summary.json", summary)
    _write_jsonl(run_dir / "task_results.jsonl", attempt_rows)
    _write_json(run_dir / "metrics.json", metrics)
    _write_json(run_dir / "pass_at_k.json", {
        "pass_at_k": pass_at_k,
        "safe_pass_at_k": safe_pass_at_k,
        "reliable": exact_reliable,
        "safe_reliable": safe_reliable,
    })
    if confidence_intervals:
        _write_json(run_dir / "confidence_intervals.json", confidence_intervals)

    if install_check:
        _write_json(run_dir / "config.json", {
            "backend": backend,
            "policy": policy,
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_seed": bootstrap_seed,
            "max_steps": max_steps,
            "attempts_per_instance": attempts_per_instance,
            "pool_size": pool_size,
            "pass_k": pass_k,
            "task_families": [spec["family_id"] for spec in tasks],
        })

    return summary


def _build_task_specs() -> list[dict[str, Any]]:
    return [
        {
            "family_id": "form_default",
            "type": "form",
            "factory": lambda attempt: DummyApkFormSearchTask(
                task_id="form_default",
                query="airport ride",
                name="Ada Lovelace",
                email="ada@example.com",
                seed=1000 + attempt,
            ),
        },
        {
            "family_id": "form_randomized",
            "type": "form",
            "factory": lambda attempt: DummyApkFormSearchTask(
                task_id="form_randomized",
                query="grocery order",
                name="Grace Hopper",
                email="grace@example.com",
                seed=1200 + attempt,
                randomization={
                    "enabled": True,
                    "button_text_variant": True,
                    "theme_variant": True,
                },
            ),
        },
        {
            "family_id": "ride_cheapest",
            "type": "ride",
            "factory": lambda attempt: RideBookingTask(
                task_id="ride_cheapest_001",
                pickup="Whitefield",
                drop="Marathahalli",
                selected_ride="Mini",
                seed=2000 + attempt,
            ),
        },
        {
            "family_id": "ride_cancel",
            "type": "ride",
            "factory": lambda attempt: RideBookingTask(
                task_id="ride_cancel_001",
                pickup="Whitefield",
                drop="Marathahalli",
                selected_ride="Mini",
                cancel_after_assignment=True,
                seed=2200 + attempt,
            ),
        },
    ]


def _run_benchmark_attempt(
    spec: dict[str, Any],
    attempt: int,
    backend: str,
    policy: str,
    max_steps: int,
    pool: DevicePool,
) -> dict[str, Any]:
    task = spec["factory"](attempt)
    attempt_started = time.perf_counter()
    with pool.lease() as device_spec:
        try:
            if spec["type"] == "form":
                result = _run_form_task(task=task, policy=policy, max_steps=max_steps, device_spec=device_spec)
            elif spec["type"] == "ride":
                result = _run_ride_task(task=task, policy=policy, device_spec=device_spec)
            else:
                raise RuntimeError(f"unknown task type: {spec['type']}")
        except Exception as exc:  # noqa: BLE001
            result = _build_failure_row(
                exception=exc,
                task_id=task.task_id,
                episode_id=getattr(task, "episode_id", ""),
                instruction=task.goal,
                attempt=attempt + 1,
                task_family=spec["family_id"],
                task_type=spec["type"],
                requested_policy=policy,
                backend=backend,
            )
        attempt_ended = time.perf_counter()
        result = {
            "task_family": spec["family_id"],
            "task_type": spec["type"],
            "instance_attempt": attempt + 1,
            "attempt_id": f"{spec['family_id']}_{attempt + 1:03d}",
            "backend": backend,
            "policy": policy if policy != "openai" or spec["type"] != "ride" else "scripted",
            "requested_policy": policy,
            "attempt_latency_seconds": max(0.0, attempt_ended - attempt_started),
            "device_serial": device_spec.serial,
            **result,
        }
    if "task_id" not in result:
        result["task_id"] = task.task_id
    return result


def _run_form_task(
    task: DummyApkFormSearchTask,
    policy: str,
    max_steps: int,
    device_spec: DeviceSpec | None = None,
) -> dict[str, Any]:
    if policy == "scripted":
        result = task.run_scripted(_adb_device(task.package, device_spec=device_spec))
        return {
            "task_id": task.task_id,
            "episode_id": result.get("episode_id", task.episode_id),
            "instruction": task.goal,
            "reward": float(result.get("reward", 0.0)),
            "final_reward": float(result.get("final_reward", result.get("reward", 0.0))),
            "exact_success": bool(result.get("final_reward", 0.0) >= 1.0),
            "success": bool(result.get("success", False)),
            "steps": len(result.get("trajectory", [])),
            "safe_success": bool(result.get("final_reward", 0.0) >= 1.0),
            "trajectory_quality": "success" if result.get("final_reward", 0.0) >= 1.0 else "partial" if result.get("reward", 0.0) > 0 else "failure",
            "invalid_action_count": 0,
            "safety_block_count": 0,
            "failure_category": "none",
            "reward_components": result.get("reward_components", {}),
            "reset_metadata": result.get("reset_metadata"),
            "rollout": {
                "final_observation": {
                    "reward_components": result.get("reward_components", {}),
                },
            },
        }

    env = _run_form_env_factory(task, max_steps=max_steps, policy_name=policy, device_spec=device_spec)
    rollout = run_rollouts(env_factory=env["factory"], policy_factory=env["policy"], episodes=1)[0]
    final = rollout.get("final_observation", {})
    prompt_tokens = rollout.get("total_prompt_tokens", 0)
    completion_tokens = rollout.get("total_completion_tokens", 0)
    return {
        "task_id": task.task_id,
        "episode_id": final.get("episode_id", task.episode_id),
        "instruction": task.goal,
        "reward": final.get("reward", rollout.get("reward", 0.0)),
        "final_reward": final.get("final_reward", rollout.get("final_reward", 0.0)),
        "exact_success": final.get("exact_success", rollout.get("success", False)),
        "success": rollout.get("success", False),
        "steps": rollout.get("steps", 0),
        "safe_success": bool(rollout.get("success", False))
        and rollout.get("failure_category") not in {"safety_block", "unsafe"},
        "trajectory_quality": rollout.get("trajectory_quality"),
        "failure_category": rollout.get("failure_category", "none"),
        "rollout": rollout,
        "invalid_action_count": rollout.get("invalid_action_count", 0),
        "safety_block_count": rollout.get("safety_block_count", 0),
        "total_prompt_tokens": prompt_tokens,
        "total_completion_tokens": completion_tokens,
        "estimated_openai_cost_usd": _estimate_cost_usd(prompt_tokens, completion_tokens),
    }


def _estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float | None:
    prompt_tokens_i = int(prompt_tokens or 0)
    completion_tokens_i = int(completion_tokens or 0)
    if prompt_tokens_i == 0 and completion_tokens_i == 0:
        return None
    # rough placeholder for reporting; can be overridden by model-specific pricing
    return (prompt_tokens_i * 1.0e-6) + (completion_tokens_i * 2.0e-6)


def _run_form_env_factory(
    task: DummyApkFormSearchTask,
    max_steps: int,
    policy_name: str,
    device_spec: DeviceSpec | None = None,
) -> dict[str, Any]:
    def env_factory() -> DummyApkEnv:
        return DummyApkEnv(
            task=task,
            device=_adb_device(task.package, device_spec=device_spec),
            max_steps=max_steps,
        )

    def policy_factory() -> Any:
        if policy_name == "openai":
            return OpenAIActionPolicy()
        return ScriptedApkPolicy(task)

    return {"factory": env_factory, "policy": policy_factory}


def _run_ride_task(task: RideBookingTask, policy: str, device_spec: DeviceSpec | None = None) -> dict[str, Any]:
    if policy == "openai":
        _run_form_task(
            DummyApkFormSearchTask(
                query="openai-unsupported-for-ride",
                name="openai",
                email="unsupported@proof",
                seed=task.seed,
            ),
            policy="scripted",
            max_steps=10,
        )
        return {
            "task_id": task.task_id,
            "episode_id": task.episode_id,
            "instruction": task.goal,
            "reward": 0.0,
            "final_reward": 0.0,
            "exact_success": False,
            "success": False,
            "steps": 0,
            "safe_success": False,
            "trajectory_quality": "unsupported_policy",
            "failure_category": "policy_not_supported",
            "invalid_action_count": 0,
            "safety_block_count": 0,
            "policy_warning": "openai policy is not supported for ride tasks in proof run; fallback scripted flow",
        }

    result = task.run_scripted(_adb_device(task.package, device_spec=device_spec))
    return {
        "task_id": result.get("task_id", task.task_id),
        "episode_id": result.get("episode_id", task.episode_id),
        "instruction": task.goal,
        "reward": float(result.get("reward", 0.0)),
        "final_reward": float(result.get("final_reward", result.get("reward", 0.0))),
        "exact_success": bool(result.get("final_reward", 0.0) >= 1.0),
        "success": bool(result.get("success", False)),
        "steps": len(result.get("trajectory", [])),
        "safe_success": bool(result.get("final_reward", 0.0) >= 1.0),
        "trajectory_quality": "success" if result.get("final_reward", 0.0) >= 1.0 else "partial" if result.get("reward", 0.0) > 0 else "failure",
        "failure_category": "none",
        "invalid_action_count": 0,
        "safety_block_count": 0,
        "reward_components": result.get("reward_components", {}),
        "reset_metadata": result.get("reset_metadata"),
    }


def _build_failure_row(
    exception: BaseException,
    *,
    task_id: str,
    episode_id: str,
    instruction: str,
    attempt: int,
    task_family: str,
    task_type: str,
    requested_policy: str,
    backend: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "episode_id": episode_id,
        "instruction": instruction,
        "reward": 0.0,
        "final_reward": 0.0,
        "exact_success": False,
        "safe_success": False,
        "success": False,
        "steps": 0,
        "task_family": task_family,
        "task_type": task_type,
        "instance_attempt": attempt,
        "attempt_id": f"{task_family}_{attempt:03d}",
        "backend": backend,
        "policy": requested_policy,
        "requested_policy": requested_policy,
        "failure_category": "runtime_error",
        "error": f"{type(exception).__name__}: {exception}",
        "invalid_action_count": 0,
        "safety_block_count": 0,
        "policy_warning": "execution_failed",
        "trajectory_quality": "runtime_error",
    }


def _compute_pass_at_k(
    groups: dict[str, list[dict[str, Any]]],
    pass_k: list[int],
    success_key: str,
) -> dict[str, float]:
    if not groups:
        return {f"pass@{k}": 0.0 for k in pass_k}

    rates: dict[str, float] = {}
    for k in pass_k:
        task_values: list[float] = []
        for rows in groups.values():
            n = len(rows)
            successes = sum(1 for row in rows if bool(row.get(success_key)))
            task_values.append(_pass_at_k_unbiased(n=n, c=successes, k=min(k, n)))
        rates[f"pass@{k}"] = mean(task_values) if task_values else 0.0
    return rates


def _pass_at_k_unbiased(n: int, c: int, k: int) -> float:
    if n <= 0:
        return 0.0
    if c <= 0:
        return 0.0
    if c > n:
        raise ValueError(f"invalid success count: c={c}, n={n}")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    if k > n:
        k = n
    if n - c < k:
        return 1.0
    return 1.0 - (math.comb(n - c, k) / math.comb(n, k))


def _compute_reliable(
    groups: dict[str, list[dict[str, Any]]],
    pass_k: list[int],
    *,
    success_key: str,
) -> dict[str, float]:
    if not groups:
        return {f"reliable@{k}": 0.0 for k in pass_k}

    return {
        f"reliable@{k}": mean(_reliable_task(rows, k, success_key=success_key) for rows in groups.values())
        for k in pass_k
    }


def _reliable_task(rows: list[dict[str, Any]], k: int, *, success_key: str) -> float:
    total = len(rows)
    successes = sum(1 for row in rows if bool(row.get(success_key)))
    return 1.0 if total >= k and successes >= k else 0.0


def _summarize_rows(
    rows: list[dict[str, Any]],
    pass_at_k: dict[str, float],
    safe_pass_at_k: dict[str, float],
    exact_reliable: dict[str, float],
    safe_reliable: dict[str, float],
    pass_k: list[int],
) -> dict[str, Any]:
    del pass_k
    if not rows:
        return {
            "exact_success_rate": 0.0,
            "safe_success_rate": 0.0,
            "avg_steps": 0.0,
            "p95_steps": 0.0,
            "avg_latency_seconds": 0.0,
            "p95_latency_seconds": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "estimated_openai_cost_usd": None,
            "cost_per_exact_success": None,
            "pass_at_k": pass_at_k,
            "safe_pass_at_k": safe_pass_at_k,
            "exact_reliable_5": exact_reliable.get("reliable@5", 0.0),
            "exact_reliable_10": exact_reliable.get("reliable@10", 0.0),
            "safe_reliable_5": safe_reliable.get("reliable@5", 0.0),
            "safe_reliable_10": safe_reliable.get("reliable@10", 0.0),
            "invalid_action_rate": 0.0,
            "safety_violation_rate": 0.0,
            "policy_not_supported_count": 0,
        }

    exact_success_rate = sum(1.0 for row in rows if row.get("exact_success")) / len(rows)
    safe_success_rate = sum(1.0 for row in rows if row.get("safe_success")) / len(rows)
    steps = [int(row.get("steps", 0) or 0) for row in rows]
    latencies = [float(row.get("attempt_latency_seconds", 0.0) or 0.0) for row in rows]
    reset_durations = [
        float((row.get("reset_metadata") or {}).get("duration_seconds", 0.0) or 0.0)
        for row in rows
        if row.get("reset_metadata") is not None
    ]
    prompt_tokens = int(sum(int(row.get("total_prompt_tokens", 0) or 0) for row in rows))
    completion_tokens = int(sum(int(row.get("total_completion_tokens", 0) or 0) for row in rows))
    estimated_costs = [float(row.get("estimated_openai_cost_usd", 0.0) or 0.0) for row in rows if row.get("estimated_openai_cost_usd") is not None]
    total_cost = sum(estimated_costs)
    exact_success_count = sum(1 for row in rows if row.get("exact_success"))

    return {
        "exact_success_rate": exact_success_rate,
        "safe_success_rate": safe_success_rate,
        "avg_steps": mean(steps),
        "p95_steps": _percentile(steps, 0.95),
        "avg_latency_seconds": mean(latencies),
        "p95_latency_seconds": _percentile(latencies, 0.95),
        "avg_reset_duration_seconds": mean(reset_durations) if reset_durations else 0.0,
        "total_prompt_tokens": prompt_tokens,
        "total_completion_tokens": completion_tokens,
        "estimated_openai_cost_usd": total_cost,
        "cost_per_exact_success": (total_cost / exact_success_count) if exact_success_count else None,
        "pass_at_k": pass_at_k,
        "safe_pass_at_k": safe_pass_at_k,
        "exact_reliable_5": exact_reliable.get("reliable@5", 0.0),
        "exact_reliable_10": exact_reliable.get("reliable@10", 0.0),
        "safe_reliable_5": safe_reliable.get("reliable@5", 0.0),
        "safe_reliable_10": safe_reliable.get("reliable@10", 0.0),
        "invalid_action_rate": _ratio(sum(int(row.get("invalid_action_count", 0) or 0) for row in rows), len(rows)),
        "safety_violation_rate": _ratio(sum(int(row.get("safety_block_count", 0) or 0) for row in rows), len(rows)),
        "policy_not_supported_count": sum(1 for row in rows if row.get("failure_category") == "policy_not_supported"),
    }


def _group_by_family(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["task_family"])].append(row)
    return grouped


def _percentile(values: list[int | float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if p <= 0:
        return ordered[0]
    if p >= 1:
        return ordered[-1]
    idx = int((len(ordered) - 1) * p)
    return ordered[idx]


def _compute_confidence_intervals(
    *,
    task_groups: dict[str, list[dict[str, Any]]],
    pass_k: list[int],
    success_key: str,
    safe_success_key: str,
    bootstrap_samples: int,
    rng: random.Random,
    seed: int,
) -> dict[str, Any]:
    if not task_groups or bootstrap_samples <= 0:
        return {}

    return {
        "bootstrap_samples": bootstrap_samples,
        "seed": seed,
        "pass_at_k": {
            f"pass@{k}": _bootstrap_ci(
                values=[_pass_at_k_unbiased(len(rows), _count_success(rows, success_key), k=min(k, len(rows))) for rows in task_groups.values()],
                samples=bootstrap_samples,
                rng=rng,
            )
            for k in pass_k
        },
        "safe_pass_at_k": {
            f"pass@{k}": _bootstrap_ci(
                values=[_pass_at_k_unbiased(len(rows), _count_success(rows, safe_success_key), k=min(k, len(rows))) for rows in task_groups.values()],
                samples=bootstrap_samples,
                rng=rng,
            )
            for k in pass_k
        },
        "reliable": {
            f"reliable@{k}": _bootstrap_ci(
                values=[_reliable_task(rows, k, success_key=success_key) for rows in task_groups.values()],
                samples=bootstrap_samples,
                rng=rng,
            )
            for k in pass_k
        },
        "safe_reliable": {
            f"safe_reliable@{k}": _bootstrap_ci(
                values=[_reliable_task(rows, k, success_key=safe_success_key) for rows in task_groups.values()],
                samples=bootstrap_samples,
                rng=rng,
            )
            for k in pass_k
        },
    }


def _count_success(rows: list[dict[str, Any]], success_key: str) -> int:
    return sum(1 for row in rows if bool(row.get(success_key)))


def _bootstrap_ci(values: list[float], samples: int, rng: random.Random) -> dict[str, float | int]:
    if not values:
        return {"mean": 0.0, "p2_5": 0.0, "p97_5": 0.0, "samples": 0}
    if samples <= 0:
        mean_value = mean(values)
        return {"mean": mean_value, "p2_5": mean_value, "p97_5": mean_value, "samples": 0}

    n = len(values)
    resampled_means: list[float] = []
    for _ in range(samples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        resampled_means.append(mean(sample))
    resampled_means.sort()
    low_idx = int((len(resampled_means) - 1) * 0.025)
    high_idx = int((len(resampled_means) - 1) * 0.975)

    return {
        "mean": mean(values),
        "p2_5": float(resampled_means[low_idx]),
        "p97_5": float(resampled_means[high_idx]),
        "samples": samples,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _adb_device(package: str, device_spec: DeviceSpec | None = None) -> AdbDevice:
    return AdbDevice(
        adb_path=os.environ.get("ADB_PATH", "adb"),
        package=package,
        serial=device_spec.serial if device_spec is not None else (os.environ.get("ADB_SERIAL") or None),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend",
        default=os.environ.get("ROLLOUT_BACKEND", "adb"),
        choices=["adb"],
    )
    parser.add_argument(
        "--policy",
        default="scripted",
        choices=["scripted", "openai"],
        help="Scripted policy is deterministic; openai policy enables model-based attempts for form tasks.",
    )
    parser.add_argument(
        "--attempts-per-instance",
        type=int,
        default=20,
        help="How many attempts to run for each task family.",
    )
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument(
        "--pass-k",
        nargs="+",
        type=int,
        default=[1, 2, 5, 10],
        help="Pass at k values, e.g. 1 2 5 10",
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=0,
        help="Bootstrap task-level confidence intervals (0 disables).",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=17230,
        help="Seed for bootstrap intervals.",
    )
    parser.add_argument("--output", default="artifacts/benchmarks", help="Directory where run artifacts are written.")
    parser.add_argument("--pool-size", type=int, default=int(os.environ.get("POOL_SIZE", "1")))
    parser.add_argument("--compact", action="store_true", help="Print compact JSON only.")
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
    )
    if args.compact:
        print(json.dumps(summary, sort_keys=True))
        return

    print("Proof benchmark completed")
    print(f"Run ID: {summary['run_id']}")
    print(f"Backend: {summary['backend']}")
    print(f"Policy: {summary['policy']}")
    print(f"Task instances: {summary['task_instances']}")
    print(f"Total attempts: {summary['total_attempts']}")
    print(f"Pass@1: {summary['pass_at_k'].get('pass@1', 0.0):.3f}")
    print(f"Safe pass@1: {summary['safe_pass_at_k'].get('pass@1', 0.0):.3f}")
    print(f"Pass@5: {summary['pass_at_k'].get('pass@5', 0.0):.3f}")
    print(f"Safe pass@5: {summary['safe_pass_at_k'].get('pass@5', 0.0):.3f}")
    print(f"Reliable@5: {summary.get('exact_reliable_5', 0.0):.3f}")
    print(f"Safe reliable@5: {summary.get('safe_reliable_5', 0.0):.3f}")
    print(f"Artifacts: {summary['output_dir']}")


if __name__ == "__main__":
    main()
