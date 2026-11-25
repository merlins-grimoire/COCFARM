"""Do not hand an early ADB connection to display/game startup."""
from pathlib import Path
import unittest
from unittest.mock import patch

from farmbot import bluestacks
from farmbot.config import DeviceConfig


class BootGuardTest(unittest.TestCase):
    def test_echo_ready_is_not_android_ready(self):
        # First ADB answers while Android boots; then boot is complete but
        # ActivityManager still has no foreground package; only then is it ready.
        states = [("0", ""), ("1", ""), ("1", "com.uncube.launcher3")]
        attempt = -1
        elapsed = 0
        checkpoints = []

        class FakeDevice:
            def connect(self):
                nonlocal attempt
                attempt += 1

            def shell(self, *args):
                if args == ("echo", "ok"):
                    return "ok\n"
                if args == ("getprop", "sys.boot_completed"):
                    return states[attempt][0] + "\n"
                raise AssertionError(args)

            def foreground_package(self):
                return states[attempt][1]

        def sleep(seconds):
            nonlocal elapsed
            elapsed += seconds

        install = bluestacks.Install(Path("unused"), Path("unused"), True,
                                      [bluestacks.Instance("TestInstance", "ExampleFarm", 5555)])
        cfg = DeviceConfig(mode="bluestacks", bluestacks_instance="TestInstance", launch_timeout=20)
        with patch.object(bluestacks, "settings_to_change", return_value={}):
            result = bluestacks.open_device(
                cfg, find=lambda: install, running=lambda: True,
                make=lambda *_: FakeDevice(), sleep=sleep, clock=lambda: elapsed,
                checkpoint=lambda: checkpoints.append(attempt))
        self.assertIsInstance(result, FakeDevice)
        self.assertEqual(attempt, 2, "Returned an ADB-ready device before Android/foreground were ready")
        self.assertEqual(elapsed, 6)
        self.assertIn(2, checkpoints, "Stop checkpoint must still run before returning")


if __name__ == "__main__":
    unittest.main()
