"""Mobile Android RL Prime package."""

from .harness import MobileAndroidHarness, load_harness
from .taskset import MobileAndroidTaskset, load_taskset


def load_environment(**kwargs):
    try:
        from prime_android_adk_rl_env import load_environment as load_prime_environment
    except ModuleNotFoundError as exc:
        if exc.name in {"verifiers", "datasets"}:
            raise RuntimeError(
                "Prime/verifiers dependencies are missing. Install with `pip install -e .` "
                "or run inside the Docker runner."
            ) from exc
        raise
    return load_prime_environment(**kwargs)


__all__ = [
    "MobileAndroidHarness",
    "MobileAndroidTaskset",
    "load_environment",
    "load_harness",
    "load_taskset",
]
