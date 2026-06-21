"""Pool-aware device allocation for concurrent rollout and benchmark work."""

from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class DeviceSpec:
    serial: str
    console_port: int | None = None
    grpc_port: int | None = None


class DevicePool:
    """Simple in-process device pool with lease-based allocation."""

    def __init__(self, devices: list[DeviceSpec]) -> None:
        if not devices:
            raise ValueError("device pool requires at least one device")
        self.devices = devices
        self._available: queue.Queue[DeviceSpec] = queue.Queue()
        self._states = {device.serial: "idle" for device in devices}
        self._lock = threading.Lock()
        for device in devices:
            self._available.put(device)

    @classmethod
    def from_environment(
        cls,
        pool_size: int | None = None,
        *,
        base_console_port: int | None = None,
        base_grpc_port: int | None = None,
    ) -> "DevicePool":
        size = max(1, int(pool_size or os.environ.get("POOL_SIZE", "1")))
        console_port = int(base_console_port or os.environ.get("ADB_BASE_CONSOLE_PORT", "5554"))
        grpc_port = int(base_grpc_port or os.environ.get("ADB_BASE_GRPC_PORT", "8554"))
        serials = _resolve_serials(size=size, base_console_port=console_port)
        devices = [
            DeviceSpec(
                serial=serial,
                console_port=_console_port_for_serial(serial, default=console_port + index * 2),
                grpc_port=grpc_port + index,
            )
            for index, serial in enumerate(serials)
        ]
        return cls(devices)

    @property
    def pool_size(self) -> int:
        return len(self.devices)

    def status(self) -> dict[str, str]:
        with self._lock:
            return dict(self._states)

    @contextmanager
    def lease(self) -> Iterator[DeviceSpec]:
        device = self._available.get()
        with self._lock:
            self._states[device.serial] = "busy"
        try:
            yield device
        finally:
            with self._lock:
                self._states[device.serial] = "idle"
            self._available.put(device)


def _resolve_serials(size: int, base_console_port: int) -> list[str]:
    serials_raw = os.environ.get("ADB_SERIALS", "").replace(",", " ")
    serials = [item.strip() for item in serials_raw.split() if item.strip()]
    if serials:
        if len(serials) < size:
            raise ValueError(f"ADB_SERIALS only provided {len(serials)} devices but pool_size={size}")
        return serials[:size]

    single = (os.environ.get("ADB_SERIAL") or "").strip()
    if size == 1:
        return [single or f"emulator-{base_console_port}"]

    if single.startswith("emulator-"):
        try:
            start = int(single.split("-", 1)[1])
        except ValueError:
            start = base_console_port
    else:
        start = base_console_port
    return [f"emulator-{start + (index * 2)}" for index in range(size)]


def _console_port_for_serial(serial: str, default: int) -> int | None:
    if serial.startswith("emulator-"):
        try:
            return int(serial.split("-", 1)[1])
        except ValueError:
            return default
    return None
