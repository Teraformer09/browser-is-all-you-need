"""Rollout runner with standardized artifacts."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.core.artifacts import ArtifactWriter
from android_adk_rl_env.core.rollout import rollout_row
from android_adk_rl_env.device_pool import DevicePool, DeviceSpec
from android_adk_rl_env.policies.openai_policy import OpenAIActionPolicy
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.tasks.ride_booking import RideBookingTask
from android_adk_rl_env.training.rollout import run_rollouts


def run_rollout_suite(
    backend: str = "adb",
    include_openai: bool = True,
    artifact_root: str = "artifacts/runs",
    pool_size: int = 1,
) -> dict[str, Any]:
    if backend != "adb":
        raise RuntimeError("rollout suite only supports the real adb backend")
    started = _now()
    writer = ArtifactWriter(root=artifact_root)
    task_run_root = writer.run_dir / "task_runs"
    task_run_root.mkdir(parents=True, exist_ok=True)
    writer.write_config(
        {
            "backend": backend,
            "include_openai": include_openai,
            "pool_size": pool_size,
            "reset_mode": os.environ.get("RESET_MODE", "snapshot"),
            "safe_mode": True,
            "tasks": ["form_default", "form_randomized", "ride_cheapest", "ride_cancel"],
        }
    )
    task_results: list[dict[str, Any]] = []
    task_plans: list[dict[str, Any]] = []

    form_tasks = [
        DummyApkFormSearchTask(task_id="form_run_001"),
        DummyApkFormSearchTask(
            task_id="form_run_002",
            query="grocery order",
            name="Grace Hopper",
            email="grace@example.com",
        ),
    ]
    for task in form_tasks:
        task_plans.append({"kind": "form", "task": task, "policy": "scripted"})

    ride_tasks = [
        RideBookingTask(task_id="ride_run_cheapest_001"),
        RideBookingTask(
            task_id="ride_run_cancel_001",
            pickup="Whitefield",
            drop="Marathahalli",
            selected_ride="Mini",
            cancel_after_assignment=True,
        ),
    ]
    for ride_task in ride_tasks:
        task_plans.append({"kind": "ride", "task": ride_task, "policy": "scripted"})

    if include_openai and os.environ.get("OPENAI_API_KEY"):
        llm_task = DummyApkFormSearchTask(task_id="form_openai_001")
        task_plans.append({"kind": "form", "task": llm_task, "policy": "openai"})

    pool = DevicePool.from_environment(pool_size=pool_size)
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool.pool_size) as executor:
        futures = [
            executor.submit(_run_task_plan, plan, backend, pool, task_run_root)
            for plan in task_plans
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            task_results.append(result)
            _write_task_result(writer, result)

    ended = _now()
    task_results.sort(key=lambda item: str(item.get("task_id", "")))
    writer.write_device_info(_device_info_for_backend(backend, task_results, pool))
    writer.write_apk_info({"package": "com.primeintellect.dummyrl", "apps": ["form", "ride_booking"]})
    writer.write_logcat("")
    writer.write_replay(task_results)
    summary = writer.write_summary(
        backend=backend,
        policy="scripted" if not os.environ.get("OPENAI_API_KEY") else "scripted+openai",
        task_results=task_results,
        started_at=started,
        ended_at=ended,
    )
    writer.ensure_required_files()
    summary["artifacts"] = str(writer.run_dir)
    summary["replay"] = str(writer.run_dir / "replay.html")
    return summary


def _adb_device_for_package(package: str) -> AdbDevice:
    return AdbDevice(
        adb_path=os.environ.get("ADB_PATH", "adb"),
        package=package,
        serial=os.environ.get("ADB_SERIAL") or None,
    )


def _adb_device_for_spec(package: str, device_spec: DeviceSpec | None) -> AdbDevice:
    if device_spec is None:
        return _adb_device_for_package(package)
    return AdbDevice(
        adb_path=os.environ.get("ADB_PATH", "adb"),
        package=package,
        serial=device_spec.serial,
    )


def _run_task_plan(
    plan: dict[str, Any],
    backend: str,
    pool: DevicePool,
    task_run_root: Path,
) -> dict[str, Any]:
    task = plan["task"]
    policy = plan["policy"]
    with pool.lease() as device_spec:
        try:
            if plan["kind"] == "form":
                result = _run_form_task(task=task, backend=backend, policy=policy, device_spec=device_spec)
            else:
                result = _run_ride_task(task=task, backend=backend, device_spec=device_spec)
        except Exception as exc:  # noqa: BLE001
            result = {
                "task_id": task.task_id,
                "episode_id": task.episode_id,
                "instruction": task.goal,
                "reward": 0.0,
                "final_reward": 0.0,
                "exact_success": False,
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "device_serial": device_spec.serial,
            }
        result["device_serial"] = device_spec.serial
        result["device_info"] = _adb_device_for_spec(task.package, device_spec).device_info()
        _write_individual_task_artifacts(task_run_root, result)
        return result


def _run_form_task(
    task: DummyApkFormSearchTask,
    backend: str,
    policy: str = "scripted",
    device_spec: DeviceSpec | None = None,
) -> dict[str, Any]:
    if policy == "scripted":
        result = task.run_scripted(_adb_device_for_spec(task.package, device_spec))
        return {
            "task_id": result.get("task_id", task.task_id),
            "episode_id": result.get("episode_id", task.episode_id),
            "instruction": task.goal,
            "reward": float(result.get("reward", 0.0)),
            "final_reward": float(result.get("final_reward", result.get("reward", 0.0))),
            "exact_success": bool(result.get("final_reward", 0.0) >= 1.0),
            "success": bool(result.get("success", False)),
            "steps": len(result.get("trajectory", [])),
            "status_text": result.get("status_text"),
            "shared_prefs": result.get("shared_prefs"),
            "reward_components": result.get("reward_components", {}),
            "reset_metadata": result.get("reset_metadata"),
        }

    def env_factory() -> DummyApkEnv:
        device = _adb_device_for_spec(task.package, device_spec)
        return DummyApkEnv(task=task, device=device, max_steps=task.max_steps)

    def policy_factory() -> Any:
        if policy == "openai":
            return OpenAIActionPolicy()
        return ScriptedApkPolicy(task)

    rollout = run_rollouts(env_factory=env_factory, policy_factory=policy_factory, episodes=1)[0]
    final = rollout.get("final_observation", {})
    return {
        "task_id": final.get("task_id", task.task_id),
        "episode_id": final.get("episode_id", task.episode_id),
        "instruction": task.goal,
        "reward": final.get("reward", rollout.get("reward", 0.0)),
        "final_reward": final.get("final_reward", rollout.get("final_reward", 0.0)),
        "exact_success": final.get("exact_success", rollout.get("success", False)),
        "success": rollout.get("success", False),
        "steps": rollout.get("steps", 0),
        "trajectory_quality": rollout.get("trajectory_quality"),
        "failure_category": rollout.get("failure_category"),
        "usable_for_rl": rollout.get("usable_for_rl"),
        "invalid_action_count": rollout.get("invalid_action_count", 0),
        "safety_block_count": rollout.get("safety_block_count", 0),
        "adb_error_count": rollout.get("adb_error_count", 0),
        "total_prompt_tokens": rollout.get("total_prompt_tokens", 0),
        "total_completion_tokens": rollout.get("total_completion_tokens", 0),
        "rollout": rollout,
    }


def _run_ride_task(task: RideBookingTask, backend: str, device_spec: DeviceSpec | None = None) -> dict[str, Any]:
    del backend
    result = task.run_scripted(_adb_device_for_spec(task.package, device_spec))
    return {
        "task_id": result.get("task_id", task.task_id),
        "episode_id": result.get("episode_id", task.episode_id),
        "instruction": task.goal,
        "reward": float(result.get("reward", 0.0)),
        "final_reward": float(result.get("final_reward", result.get("reward", 0.0))),
        "exact_success": bool(result.get("final_reward", 0.0) >= 1.0),
        "success": bool(result.get("success", False)),
        "steps": len(result.get("trajectory", [])),
        "status_text": result.get("status_text"),
        "shared_prefs": result.get("shared_prefs"),
        "reward_components": result.get("reward_components", {}),
        "reset_metadata": result.get("reset_metadata"),
    }


class SequencePolicy:
    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.index = 0

    def reset(self) -> None:
        self.index = 0

    def act(self, observation: dict[str, Any]):
        del observation
        if self.index >= len(self.actions):
            return ApkAction("finish")
        action = self.actions[self.index]
        self.index += 1
        return ApkAction.from_dict(action)


def _write_task_result(writer: ArtifactWriter, result: dict[str, Any]) -> None:
    rollout = result.get("rollout")
    if rollout:
        for transition in rollout.get("transitions", []):
            observation = transition.get("observation", {})
            info = transition.get("info", {})
            row = rollout_row(
                episode_id=observation.get("episode_id", result.get("episode_id", "")),
                task_id=observation.get("task_id", result.get("task_id", "")),
                step=int(observation.get("steps", 0)),
                observation=observation,
                action=transition.get("action", {}),
                reward=float(transition.get("reward", 0.0)),
                done=bool(transition.get("done", False)),
                info=info,
            )
            writer.append_rollout(row)
            writer.append_reward(
                {
                    "episode_id": row["episode_id"],
                    "task_id": row["task_id"],
                    "step": row["step"],
                    "reward": row["reward"],
                    "exact_success": info.get("exact_success", False),
                    "reward_components": info.get("reward_components", {}),
                }
            )
        return
    writer.append_rollout(
        rollout_row(
            episode_id=result.get("episode_id", ""),
            task_id=result.get("task_id", ""),
            step=int(result.get("steps", 0)),
            observation={
                "instruction": result.get("instruction"),
                "simulated_app": result.get("simulated_app"),
                "reset_metadata": result.get("reset_metadata"),
            },
            action={"type": "scripted_rollout"},
            reward=float(result.get("reward", 0.0)),
            done=True,
            info={
                "exact_success": result.get("exact_success", False),
                "expected_state": result.get("expected_state", {}),
                "reward_components": result.get("reward_components", {}),
            },
        )
    )
    writer.append_reward(
        {
            "episode_id": result.get("episode_id", ""),
            "task_id": result.get("task_id", ""),
            "step": int(result.get("steps", 0)),
            "reward": float(result.get("reward", 0.0)),
            "exact_success": result.get("exact_success", False),
            "reward_components": result.get("reward_components", {"simulated_ride_flow": bool(result.get("exact_success", False))}),
        }
    )


def _write_individual_task_artifacts(task_run_root: Path, result: dict[str, Any]) -> None:
    run_id = f"{result.get('task_id', 'task')}_{result.get('episode_id', 'episode')}"
    writer = ArtifactWriter(root=task_run_root, run_id=run_id)
    writer.write_config(
        {
            "task_id": result.get("task_id"),
            "episode_id": result.get("episode_id"),
            "instruction": result.get("instruction"),
            "device_serial": result.get("device_serial"),
        }
    )
    _write_task_result(writer, result)
    writer.write_device_info(result.get("device_info", {}))
    writer.write_apk_info({"package": "com.primeintellect.dummyrl"})
    writer.write_logcat("")
    writer.write_replay([result])
    started = ended = _now()
    writer.write_summary(
        backend="adb",
        policy="scripted" if "openai" not in str(result.get("task_id")) else "openai",
        task_results=[result],
        started_at=started,
        ended_at=ended,
    )
    writer.ensure_required_files()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _device_info_for_backend(backend: str, task_results: list[dict[str, Any]], pool: DevicePool) -> dict[str, Any]:
    if backend != "adb":
        return {"backend": backend}
    serials = []
    for result in task_results:
        if result.get("device_serial"):
            serials.append(result["device_serial"])
            continue
        rollout = result.get("rollout", {})
        final = rollout.get("final_observation", {})
        if final.get("serial"):
            serials.append(final["serial"])
    return {
        "backend": backend,
        "pool_size": pool.pool_size,
        "serials": serials,
        "unique_serial_count": len(set(serials)),
        "pool_state": pool.status(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=os.environ.get("ROLLOUT_BACKEND", "adb"), choices=["adb"])
    parser.add_argument("--artifact-root", default="artifacts/runs")
    parser.add_argument("--no-openai", action="store_true")
    parser.add_argument("--pool-size", type=int, default=int(os.environ.get("POOL_SIZE", "1")))
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    summary = run_rollout_suite(
        backend=args.backend,
        include_openai=not args.no_openai,
        artifact_root=args.artifact_root,
        pool_size=args.pool_size,
    )
    if args.compact:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("Rollout run completed")
        print(f"Run ID: {summary['run_id']}")
        print(f"Backend: {summary['backend']}")
        print(f"Tasks: {summary['task_count']}")
        print(f"Success rate: {summary['success_rate']}")
        print(f"Artifacts: {summary['artifacts']}")
        print(f"Replay: {summary['replay']}")


if __name__ == "__main__":
    main()
