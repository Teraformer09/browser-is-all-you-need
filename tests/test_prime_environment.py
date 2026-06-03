"""Tests for the Prime/verifiers environment entry point."""

from __future__ import annotations

import unittest


class PrimeEnvironmentTest(unittest.TestCase):
    def test_load_environment_when_verifiers_installed(self) -> None:
        try:
            from prime_android_adk_rl_env import load_environment
        except ModuleNotFoundError as exc:
            if exc.name in {"verifiers", "datasets"}:
                self.skipTest(f"optional Prime SDK dependency missing: {exc.name}")
            raise

        env = load_environment(backend="adb", max_examples=1, max_turns=3)
        self.assertEqual(env.env_id, "prime-android-apk-adk")
        self.assertEqual(env.max_turns, 3)
        self.assertEqual(env.get_dataset().num_rows, 1)


if __name__ == "__main__":
    unittest.main()
