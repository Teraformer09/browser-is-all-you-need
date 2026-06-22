"""Registered success and reward checks for task specs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

CheckFn = Callable[[dict[str, Any], dict[str, Any]], float]

CHECKS: dict[str, CheckFn] = {}


def register_check(name: str) -> Callable[[CheckFn], CheckFn]:
    def decorator(func: CheckFn) -> CheckFn:
        CHECKS[name] = func
        return func

    return decorator


def get_check(name: str) -> CheckFn:
    if name not in CHECKS:
        raise KeyError(f"unknown registered check: {name}")
    return CHECKS[name]


from android_adk_rl_env.tasks.checks import dummy_apk as _dummy_apk  # noqa: E402,F401
from android_adk_rl_env.tasks.checks import ride_booking as _ride_booking  # noqa: E402,F401

__all__ = ["CHECKS", "CheckFn", "get_check", "register_check"]
