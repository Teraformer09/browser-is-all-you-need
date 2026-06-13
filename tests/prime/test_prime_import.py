import unittest


class PrimeImportTest(unittest.TestCase):
    def test_mobile_android_package_imports_without_adb(self) -> None:
        from environments.mobile_android_rl.mobile_android_rl import load_harness, load_taskset

        harness = load_harness()
        taskset = load_taskset(split="eval", app="form")

        self.assertEqual(harness.backend, "adb")
        self.assertGreater(len(taskset), 0)


if __name__ == "__main__":
    unittest.main()
