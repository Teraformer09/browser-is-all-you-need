"""Docker ADB provider alias.

Docker containers use the same ADB implementation, usually pointed at a host ADB
server through `ADB_SERVER_SOCKET` or explicit network configuration.
"""

from android_adk_rl_env.adb_device import AdbDevice as DockerAdbDevice

__all__ = ["DockerAdbDevice"]
