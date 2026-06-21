import os
import unittest

from android_adk_rl_env.device_pool import DevicePool


class DevicePoolTest(unittest.TestCase):
    def test_expands_emulator_pool_from_size(self) -> None:
        old_pool = os.environ.get("POOL_SIZE")
        old_serials = os.environ.get("ADB_SERIALS")
        old_serial = os.environ.get("ADB_SERIAL")
        try:
            os.environ["POOL_SIZE"] = "3"
            os.environ.pop("ADB_SERIALS", None)
            os.environ["ADB_SERIAL"] = "emulator-5554"
            pool = DevicePool.from_environment()
            self.assertEqual([device.serial for device in pool.devices], ["emulator-5554", "emulator-5556", "emulator-5558"])
        finally:
            if old_pool is None:
                os.environ.pop("POOL_SIZE", None)
            else:
                os.environ["POOL_SIZE"] = old_pool
            if old_serials is None:
                os.environ.pop("ADB_SERIALS", None)
            else:
                os.environ["ADB_SERIALS"] = old_serials
            if old_serial is None:
                os.environ.pop("ADB_SERIAL", None)
            else:
                os.environ["ADB_SERIAL"] = old_serial


if __name__ == "__main__":
    unittest.main()
