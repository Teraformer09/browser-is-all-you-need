"""Explicit CPU modes: never silently replace KVM with software emulation."""


def runtime_options(acceleration="kvm"):
    if not isinstance(acceleration, str) or acceleration not in {"kvm", "software"}:
        raise ValueError("acceleration must be 'kvm' or 'software'")
    software = acceleration == "software"
    return {
        "acceleration": acceleration,
        "requires_kvm": not software,
        "system_image": "system-images;android-33;default;x86_64" if software else "system-images;android-33;google_apis;x86_64",
        "boot_timeout_seconds": 600 if software else 240,
        "exchange_timeout_seconds": 1200 if software else 420,
        "package_ready_timeout_seconds": 120 if software else 0,
        "install_timeout_seconds": 180 if software else 60,
        "startup_ui_timeout_seconds": 240 if software else 0,
        "startup_idle_seconds": 60 if software else 0,
        "system_ui_recovery": "restart" if software else "wait",
        "sandbox_timeout_minutes": 30 if software else 20,
        "episode_timeout_seconds": 1680 if software else 900,
        "cores": 1 if software else 4,
        "memory_mb": 4096,
        "gpu": "swiftshader" if software else "swiftshader_indirect",
        "accel": "off" if software else "on",
    }


def emulator_command(emulator, acceleration="kvm"):
    options = runtime_options(acceleration)
    return [str(emulator), "-avd", "democart", "-port", "5556",
            "-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot",
            "-accel", options["accel"], "-gpu", options["gpu"],
            "-memory", str(options["memory_mb"]), "-cores", str(options["cores"])]

