"""Harness abstraction separate from taskset/reward definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from android_adk_rl_env.envs.mobile_task_env import make_mobile_task_env
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask


@dataclass
class MobileAndroidHarness:
    backend: str = "adb"
    observation_mode: str = "compact_text"
    max_steps: int = 15

    def make_env(self, **kwargs: Any):
        task = kwargs.pop("task", DummyApkFormSearchTask(max_steps=self.max_steps))
        return make_mobile_task_env(
            backend=self.backend,
            task=task,
            max_steps=self.max_steps,
            observation_mode=self.observation_mode,
            **kwargs,
        )


def load_harness(backend: str = "adb", observation_mode: str = "compact_text", max_steps: int = 15, **kwargs: Any) -> MobileAndroidHarness:
    del kwargs
    return MobileAndroidHarness(backend=backend, observation_mode=observation_mode, max_steps=max_steps)
