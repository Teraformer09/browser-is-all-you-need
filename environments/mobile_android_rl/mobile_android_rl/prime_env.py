"""Prime environment compatibility exports."""

try:
    from prime_android_adk_rl_env import PrimeAndroidApkEnv, load_environment
except ModuleNotFoundError as exc:  # pragma: no cover - exercised when optional deps are absent.
    if exc.name in {"verifiers", "datasets"}:
        PrimeAndroidApkEnv = None  # type: ignore[assignment]

        def load_environment(**kwargs):  # type: ignore[no-redef]
            del kwargs
            raise RuntimeError("Prime/verifiers dependencies are missing. Install `verifiers` and `datasets`.")

    else:
        raise

__all__ = ["PrimeAndroidApkEnv", "load_environment"]
