"""Reconstruct the late-recovery timing, not a model trajectory or original UI."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amazon_improved_task_001.harness.emulator_config import runtime_options
from amazon_improved_task_001.harness.startup_ui import prepare_startup_ui

CLOSE = '''<hierarchy><node package="android" resource-id="android:id/alertTitle"
text="System UI isn't responding"/><node package="android" resource-id="android:id/aerr_close"
text="Close app" enabled="true" clickable="true" bounds="[70,1143][1010,1269]"/></hierarchy>'''
CLEAN = '<hierarchy><node package="com.android.launcher3" text="Home"/></hierarchy>'

class StartupBudgetRegressionTests(unittest.TestCase):
    def run_late_recovery(self, budget, permanently_empty=False):
        clock, calls, dumps, pids = [0.0], [], [0], [0]
        with tempfile.TemporaryDirectory() as temp:
            def sleep(seconds):
                clock[0] += seconds
            def command(args, timeout):
                calls.append(args)
                duration = 0.1
                if 'dump' in args:
                    dumps[0] += 1
                    duration = 10 if dumps[0] == 1 else 10.5 if dumps[0] <= 8 else 2 if dumps[0] == 9 else 5
                elif 'cat' in args:
                    duration = 0.4
                if duration > timeout:
                    clock[0] += timeout
                    raise subprocess.TimeoutExpired(args, timeout)
                clock[0] += duration
                if 'dump' in args:
                    if dumps[0] > 1 and (dumps[0] <= 8 or permanently_empty):
                        return ''
                    return 'UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml'
                if 'cat' in args:
                    return CLOSE if dumps[0] == 1 else CLEAN
                if 'pidof' in args:
                    pids[0] += 1
                    return '898' if pids[0] == 1 else '2524'
                return ''
            error = None
            with patch('time.monotonic', side_effect=lambda: clock[0]), patch('time.sleep', side_effect=sleep):
                try:
                    prepare_startup_ui(Path(temp), command, budget_seconds=budget,
                                       initial_idle_seconds=60, recovery='restart')
                except Exception as exc:
                    error = exc
            report = json.loads((Path(temp) / 'startup/manifest.json').read_text())
            return report, calls, error

    def test_late_clean_ui_gets_full_quiet_window_without_another_tap(self):
        old, _, error = self.run_late_recovery(180)
        self.assertIsNotNone(error)
        self.assertEqual(old['status'], 'FAILED')
        self.assertTrue(old['process_restart_verified'])
        config = runtime_options('software')
        self.assertEqual(config['startup_ui_timeout_seconds'], 240)
        new, calls, error = self.run_late_recovery(config['startup_ui_timeout_seconds'])
        self.assertIsNone(error)
        self.assertEqual(new['status'], 'READY')
        self.assertTrue(new['process_restart_verified'])
        self.assertGreater(new['elapsed_seconds'], 180)
        self.assertLess(new['elapsed_seconds'], 240)
        self.assertEqual(len([c for c in calls if 'input' in c]), 1)
        self.assertFalse(new['task_episode_started'])
        self.assertEqual(config['sandbox_timeout_minutes'], 30)
        self.assertEqual(config['episode_timeout_seconds'], 1680)
        self.assertEqual(config['exchange_timeout_seconds'], 1200)

    def test_extended_readiness_still_stops_on_permanently_missing_ui(self):
        report, calls, error = self.run_late_recovery(240, permanently_empty=True)
        self.assertIsNotNone(error)
        self.assertEqual(report['status'], 'FAILED')
        self.assertLessEqual(report['elapsed_seconds'], 240)
        self.assertFalse(report['process_restart_verified'])
        self.assertEqual(len([c for c in calls if 'input' in c]), 1)

if __name__ == '__main__':
    unittest.main()
