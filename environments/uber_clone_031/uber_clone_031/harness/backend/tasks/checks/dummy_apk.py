"""Dummy APK registered checks."""

from __future__ import annotations

from typing import Any

from uber_clone_031.harness.backend.tasks.checks import register_check


@register_check("dummy_form_exact")
def dummy_form_exact(observation: dict[str, Any], _: dict[str, Any]) -> float:
    return 1.0 if bool(observation.get("exact_success", False)) else 0.0


@register_check("dummy_form_fractional")
def dummy_form_fractional(observation: dict[str, Any], _: dict[str, Any]) -> float:
    return float(observation.get("reward", 0.0) or 0.0)
