"""Shared task-spec execution helpers for CLI and benchmarks."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import DummyApkEnv
from android_adk_rl_env.policies.openai_policy import OpenAIActionPolicy
from android_adk_rl_env.policies.random import RandomApkPolicy
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy
from android_adk_rl_env.task_specs import EvalTaskSpec, build_known_task
from android_adk_rl_env.tasks.checks import get_check
from android_adk_rl_env.training.rollout import run_rollouts


def run_task_spec(
    spec: EvalTaskSpec,
    *,
    policy: str = "scripted",
    backend: str = "adb",
    serial: str | None = None,
    attempt: int = 0,
    install_apk: bool = True,
    healthcheck: bool = True,
    max_steps: int | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    if backend != "adb":
        raise RuntimeError(f"unsupported backend for current live path: {backend}")

    task = build_known_task(spec, attempt=attempt)
    if task is None:
        raise RuntimeError(f"task spec {spec.task_id} is not mapped to a runnable task type")

    resolved_serial = serial or os.environ.get("ADB_SERIAL") or resolve_adb_serial(os.environ.get("ADB_PATH", "adb"))
    device = AdbDevice(
        adb_path=os.environ.get("ADB_PATH", "adb"),
        package=spec.app.package,
        serial=resolved_serial or None,
    )
    health = run_device_healthcheck(device, package=spec.app.package) if healthcheck else {"skipped": True}
    if install_apk and spec.app.apk_path:
        device.install_apk(spec.app.apk_path)

    if policy == "scripted":
        raw = task.run_scripted(device)
        final_observation = {
            "task_id": raw.get("task_id", spec.task_id),
            "episode_id": raw.get("episode_id"),
            "task": raw.get("task"),
            "goal": raw.get("goal", spec.goal),
            "reward": float(raw.get("reward", 0.0)),
            "final_reward": float(raw.get("final_reward", raw.get("reward", 0.0))),
            "exact_success": bool(raw.get("final_reward", 0.0) >= 1.0),
            "reward_components": raw.get("reward_components", {}),
            "shared_prefs": raw.get("shared_prefs", ""),
            "reset_metadata": raw.get("reset_metadata"),
            "trajectory": raw.get("trajectory", []),
        }
        policy_metadata: dict[str, Any] = {}
    else:
        if spec.task_type != "dummy_form":
            raise RuntimeError(f"policy {policy} is only supported for dummy_form in the current live path")

        def env_factory() -> DummyApkEnv:
            return DummyApkEnv(
                task=task,  # type: ignore[arg-type]
                device=AdbDevice(
                    adb_path=os.environ.get("ADB_PATH", "adb"),
                    package=spec.app.package,
                    serial=device.serial,
                ),
                max_steps=max_steps or spec.max_steps,
            )

        def policy_factory() -> Any:
            if policy == "openai":
                return OpenAIActionPolicy()
            if policy == "random":
                return RandomApkPolicy(seed=attempt + 7)
            return ScriptedApkPolicy(task)  # pragma: no cover - defensive fallback

        rollout = run_rollouts(env_factory=env_factory, policy_factory=policy_factory, episodes=1)[0]
        final_observation = dict(rollout.get("final_observation", {}))
        final_observation["trajectory"] = rollout.get("transitions", [])
        policy_metadata = {
            "total_prompt_tokens": int(rollout.get("total_prompt_tokens", 0) or 0),
            "total_completion_tokens": int(rollout.get("total_completion_tokens", 0) or 0),
            "estimated_openai_cost_usd": rollout.get("estimated_openai_cost_usd"),
        }

    success_score = evaluate_success(spec, final_observation)
    reward_value = _select_reward(spec, final_observation)
    ended = time.perf_counter()

    return {
        "task_id": spec.task_id,
        "benchmark_family": spec.family_id,
        "task_type": spec.task_type,
        "goal": spec.goal,
        "policy": policy,
        "backend": backend,
        "healthcheck": health,
        "reward": reward_value,
        "final_reward": float(final_observation.get("final_reward", reward_value)),
        "success_score": success_score,
        "success_threshold": spec.success.threshold,
        "success_type": spec.success.type,
        "success_check": spec.success.check,
        "exact_success": bool(success_score >= spec.success.threshold),
        "task_success": bool(success_score >= spec.success.threshold),
        "steps": int(final_observation.get("steps", len(final_observation.get("trajectory", []))) or 0),
        "episode_id": final_observation.get("episode_id"),
        "reward_components": final_observation.get("reward_components", {}),
        "trajectory": final_observation.get("trajectory", []),
        "reset_metadata": final_observation.get("reset_metadata"),
        "attempt_latency_seconds": max(0.0, ended - started),
        "device_serial": device.serial,
        **policy_metadata,
    }


def evaluate_success(spec: EvalTaskSpec, observation: dict[str, Any]) -> float:
    if spec.success.type == "registered_check":
        return float(get_check(spec.success.check)(observation, spec.parameters))
    if spec.success.type == "expression":
        return 1.0 if _evaluate_expression(spec.success.check, observation) else 0.0
    raise RuntimeError(f"unsupported success type: {spec.success.type}")


def run_device_healthcheck(device: AdbDevice, *, package: str) -> dict[str, Any]:
    device.wait_for_ready()
    api_level = device.adb("shell", "getprop", "ro.build.version.sdk", check=False).stdout.strip()
    boot_completed = device.adb("shell", "getprop", "sys.boot_completed", check=False).stdout.strip()
    package_installed = device.adb("shell", "pm", "path", package, check=False)
    return {
        "serial": device.serial,
        "api_level": api_level,
        "boot_completed": boot_completed,
        "package_installed": package_installed.returncode == 0 and bool(package_installed.stdout.strip()),
    }


def resolve_adb_serial(adb_path: str) -> str | None:
    result = subprocess.run(
        [adb_path, "devices"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def _select_reward(spec: EvalTaskSpec, observation: dict[str, Any]) -> float:
    if spec.reward.mode == "fractional":
        return float(observation.get("reward", 0.0) or 0.0)
    return float(observation.get("final_reward", observation.get("reward", 0.0)) or 0.0)


def _evaluate_expression(expression: str, observation: dict[str, Any]) -> bool:
    raw_prefs = str(observation.get("shared_prefs", ""))
    prefs = _parse_prefs_like_state(raw_prefs)
    expr = expression.strip()
    if "==" not in expr:
        raise RuntimeError(f"unsupported success expression: {expression}")
    left, right = [part.strip() for part in expr.split("==", 1)]
    if not left.startswith("prefs."):
        raise RuntimeError(f"unsupported success expression: {expression}")
    key = left.removeprefix("prefs.").strip()
    expected = right.strip().strip('"').strip("'").lower()
    actual = str(prefs.get(key, "")).strip().lower()
    return actual == expected


def _parse_prefs_like_state(raw: str) -> dict[str, str]:
    state: dict[str, str] = {}
    for name in ("episode_id", "query", "name", "email", "screen", "submitted", "ride_pickup", "ride_drop", "selected_ride", "ride_confirmed", "ride_cancelled", "payment", "coupon"):
        marker = f'name="{name}"'
        if marker not in raw:
            continue
        fragment = raw.split(marker, 1)[1]
        if "value=" in fragment:
            value = fragment.split('value="', 1)[1].split('"', 1)[0]
        elif ">" in fragment and "</" in fragment:
            value = fragment.split(">", 1)[1].split("</", 1)[0]
        else:
            value = ""
        state[name] = value
    return state
