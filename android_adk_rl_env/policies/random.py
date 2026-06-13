"""Random policy for smoke-testing action validation."""

from __future__ import annotations

import random
from typing import Any

from android_adk_rl_env.apk_env import ApkAction


class RandomApkPolicy:
    """Samples from a small valid action set using visible resource IDs."""

    def __init__(self, seed: int = 7) -> None:
        self.rng = random.Random(seed)

    def reset(self) -> None:
        return None

    def act(self, observation: dict[str, Any]) -> ApkAction:
        targets = [node.get("id") for node in observation.get("ui", []) if isinstance(node, dict) and node.get("id")]
        editable = [target for target in targets if str(target).endswith("_input")]
        clickable = [target for target in targets if not str(target).endswith("_result") and not str(target).endswith("_text")]
        choices: list[ApkAction] = [ApkAction("wait"), ApkAction("press_back")]
        choices.extend(ApkAction("click_resource", target=str(target)) for target in clickable)
        choices.extend(ApkAction("input_resource", target=str(target), text="sample") for target in editable)
        return self.rng.choice(choices)


__all__ = ["RandomApkPolicy"]
