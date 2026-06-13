"""Task lifecycle hooks inspired by benchmark environments such as AndroidWorld."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class SupportsTaskLifecycle(Protocol):
    def initialize_task(self, device: Any) -> None: ...
    def reset_episode(self, device: Any) -> None: ...
    def verify_success(self, observation: dict[str, Any]) -> bool: ...
    def teardown_task(self, device: Any) -> None: ...


@dataclass(frozen=True)
class NoopTaskLifecycle:
    def initialize_task(self, device: Any) -> None:
        del device

    def reset_episode(self, device: Any) -> None:
        del device

    def verify_success(self, observation: dict[str, Any]) -> bool:
        return bool(observation.get("exact_success", False))

    def teardown_task(self, device: Any) -> None:
        del device
