"""Typed runtime errors."""


class DeviceResetError(RuntimeError):
    """Raised when a backend cannot reset the mobile app safely."""
