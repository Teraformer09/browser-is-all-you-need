"""Factory for mobile task environments."""

from __future__ import annotations

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.apk_env import DummyApkEnv
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


def make_mobile_task_env(backend: str = "adb", task: DummyApkFormSearchTask | None = None, **kwargs: object) -> DummyApkEnv:
    task = task or DummyApkFormSearchTask()
    if backend == "adb":
        return DummyApkEnv(task=task, device=AdbDevice(package=task.package), **kwargs)
    raise ValueError(f"unsupported backend: {backend}")
