"""Rollout runner with standardized artifacts."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.core.artifacts import ArtifactWriter
from android_adk_rl_env.core.rollout import rollout_row
from android_adk_rl_env.policies.openai_policy import OpenAIActionPolicy
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.tasks.ride_booking import RideBookingTask
from android_adk_rl_env.training.rollout import run_rollouts


def run_rollout_suite(
    backend: str = "adb",
    include_openai: bool = True,
    artifact_root: str = "artifacts/runs",
) -> dict[str, Any]:
    if backend != "adb":
        raise RuntimeError("rollout suite only supports the real adb backend")
    started = _now()
    writer = ArtifactWriter(root=artifact_root)
    writer.write_config(
        {
            "backend": backend,
            "include_openai": include_openai,
            "safe_mode": True,
            "tasks": ["form_default", "form_randomized", "ride_cheapest", "ride_cancel"],
        }
    )
    task_results: list[dict[str, Any]] = []

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
        result = _run_form_task(task=task, backend=backend)
        task_results.append(result)
        _write_task_result(writer, result)

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
        ride = _run_ride_task(task=ride_task, backend=backend)
        task_results.append(ride)
        _write_task_result(writer, ride)

    if include_openai and os.environ.get("OPENAI_API_KEY"):
        llm_task = DummyApkFormSearchTask(task_id="form_openai_001")
        try:
            result = _run_form_task(task=llm_task, backend=backend, policy="openai")
        except Exception as exc:  # noqa: BLE001
            result = {
                "task_id": llm_task.task_id,
                "episode_id": llm_task.episode_id,
                "instruction": llm_task.goal,
                "reward": 0.0,
                "exact_success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        task_results.append(result)
        _write_task_result(writer, result)

    ended = _now()
    writer.write_device_info(_device_info_for_backend(backend, task_results))
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


def _run_form_task(task: DummyApkFormSearchTask, backend: str, policy: str = "scripted") -> dict[str, Any]:
    def env_factory() -> DummyApkEnv:
        device = AdbDevice(package=task.package)
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
        "usable_for_sft": rollout.get("usable_for_sft"),
        "usable_for_rl": rollout.get("usable_for_rl"),
        "invalid_action_count": rollout.get("invalid_action_count", 0),
        "safety_block_count": rollout.get("safety_block_count", 0),
        "adb_error_count": rollout.get("adb_error_count", 0),
        "sft_usable_step_count": rollout.get("sft_usable_step_count", 0),
        "total_prompt_tokens": rollout.get("total_prompt_tokens", 0),
        "total_completion_tokens": rollout.get("total_completion_tokens", 0),
        "rollout": rollout,
    }


def _run_ride_task(task: RideBookingTask, backend: str) -> dict[str, Any]:
    def env_factory() -> DummyApkEnv:
        device = AdbDevice(package=task.package)
        return DummyApkEnv(task=task, device=device, max_steps=task.max_steps)

    rollout = run_rollouts(env_factory=env_factory, policy_factory=lambda: SequencePolicy(task.action_sequence()), episodes=1)[0]
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
        "usable_for_sft": rollout.get("usable_for_sft"),
        "usable_for_rl": rollout.get("usable_for_rl"),
        "invalid_action_count": rollout.get("invalid_action_count", 0),
        "safety_block_count": rollout.get("safety_block_count", 0),
        "adb_error_count": rollout.get("adb_error_count", 0),
        "sft_usable_step_count": rollout.get("sft_usable_step_count", 0),
        "total_prompt_tokens": rollout.get("total_prompt_tokens", 0),
        "total_completion_tokens": rollout.get("total_completion_tokens", 0),
        "rollout": rollout,
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
            observation={"instruction": result.get("instruction"), "simulated_app": result.get("simulated_app")},
            action={"type": "scripted_rollout"},
            reward=float(result.get("reward", 0.0)),
            done=True,
            info={"exact_success": result.get("exact_success", False), "expected_state": result.get("expected_state", {})},
        )
    )
    writer.append_reward(
        {
            "episode_id": result.get("episode_id", ""),
            "task_id": result.get("task_id", ""),
            "step": int(result.get("steps", 0)),
            "reward": float(result.get("reward", 0.0)),
            "exact_success": result.get("exact_success", False),
            "reward_components": {"simulated_ride_flow": bool(result.get("exact_success", False))},
        }
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _device_info_for_backend(backend: str, task_results: list[dict[str, Any]]) -> dict[str, Any]:
    if backend != "adb":
        return {"backend": backend}
    for result in task_results:
        rollout = result.get("rollout", {})
        final = rollout.get("final_observation", {})
        if final:
            return {
                "backend": backend,
                "serial": final.get("serial", ""),
                "package": final.get("package", "com.primeintellect.dummyrl"),
                "screen": final.get("screen"),
            }
    return {"backend": backend}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=os.environ.get("ROLLOUT_BACKEND", "adb"), choices=["adb"])
    parser.add_argument("--artifact-root", default="artifacts/runs")
    parser.add_argument("--no-openai", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    summary = run_rollout_suite(
        backend=args.backend,
        include_openai=not args.no_openai,
        artifact_root=args.artifact_root,
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
