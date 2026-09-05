"""Ride-booking registered checks."""

from __future__ import annotations

from typing import Any

from uber_clone_031.harness.backend.tasks.checks import register_check


@register_check("ride_booking_exact")
def ride_booking_exact(observation: dict[str, Any], _: dict[str, Any]) -> float:
    return 1.0 if bool(observation.get("exact_success", False)) else 0.0


@register_check("ride_booking_fractional")
def ride_booking_fractional(observation: dict[str, Any], _: dict[str, Any]) -> float:
    return float(observation.get("reward", 0.0) or 0.0)
