"""VLM screenshot policy interface placeholder.

This policy keeps the public API ready for screenshot-capable agents while
making no network calls unless a concrete provider is supplied later.
"""

from __future__ import annotations

from typing import Any

from android_adk_rl_env.apk_env import ApkAction


class ScreenshotVlmPolicy:
    def reset(self) -> None:
        return None

    def act(self, observation: dict[str, Any]) -> ApkAction:
        if not observation.get("screenshot_path"):
            return ApkAction("wait")
        return ApkAction("wait")


__all__ = ["ScreenshotVlmPolicy"]
