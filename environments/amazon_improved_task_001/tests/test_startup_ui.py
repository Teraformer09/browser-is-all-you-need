"""Startup-only recovery never suppresses app errors or scores a task."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from amazon_improved_task_001.harness.startup_ui import prepare_startup_ui, system_ui_wait_target, system_ui_restart_target

SYSTEM = """<hierarchy><node package="android" resource-id="android:id/alertTitle"
text="System UI isn't responding"/><node package="android" resource-id="android:id/aerr_wait"
text="Wait" enabled="true" clickable="true" bounds="[70,1269][1010,1395]"/></hierarchy>"""
CLEAN = '<hierarchy><node package="com.android.launcher3" text="Home"/></hierarchy>'

class StartupUiTests(unittest.TestCase):
    def test_exact_system_dialog_only(self):
        self.assertEqual(system_ui_wait_target(SYSTEM), (540, 1332))
        self.assertIsNone(system_ui_wait_target(CLEAN))
        for xml in (SYSTEM.replace("System UI", "DemoCart"), SYSTEM.replace('package="android"', 'package="spoof"')):
            with self.subTest(xml=xml), self.assertRaises(RuntimeError):
                system_ui_wait_target(xml)

    def test_invalid_wait_controls_fail_closed(self):
        for xml in (SYSTEM.replace('enabled="true"', 'enabled="false"'),
                    SYSTEM.replace('[70,1269][1010,1395]', '[70,1269][1100,1395]'),
                    SYSTEM.replace('</hierarchy>', SYSTEM.split('<hierarchy>')[1])):
            with self.subTest(xml=xml), self.assertRaises((RuntimeError, ValueError)):
                system_ui_wait_target(xml)

    def run_gate(self, snapshots, empty_dumps=0):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root, calls, counter = Path(temp.name), [], [0]
        def monotonic():
            counter[0] += 1
            return counter[0] * 1.0
        pending_empty = [empty_dumps]
        def command(args, **kwargs):
            calls.append(args)
            if "dump" in args:
                if pending_empty[0]:
                    pending_empty[0] -= 1
                    return ""
                return "UI hierchary dumped to: /sdcard/democart-startup-ui.xml"
            if "cat" in args:
                return snapshots.pop(0) if len(snapshots) > 1 else snapshots[0]
            return ""
        with patch("time.monotonic", side_effect=monotonic), patch("time.sleep"):
            result = prepare_startup_ui(root, command)
        return result, calls, root

    def test_wait_is_logged_before_episode_and_not_repeated(self):
        result, calls, root = self.run_gate([SYSTEM, CLEAN])
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["system_wait_taps"], 1)
        self.assertFalse(result["task_episode_started"])
        taps = [c for c in calls if "input" in c]
        self.assertEqual(taps, [["adb", "-s", "emulator-5556", "shell", "input", "tap", "540", "1332"]])
        self.assertEqual(json.loads((root / "startup/manifest.json").read_text()), result)
        self.assertFalse((root / "episodes").exists())

    def test_clean_startup_never_taps(self):
        result, calls, _ = self.run_gate([CLEAN])
        self.assertEqual(result["system_wait_taps"], 0)
        self.assertFalse(any("input" in c for c in calls))

    def test_persistent_system_anr_fails_instead_of_hiding_it(self):
        with self.assertRaisesRegex(RuntimeError, "REPEATED_SYSTEM_UI_ANR"):
            self.run_gate([SYSTEM])

    def test_other_crash_dialog_is_not_treated_as_clean(self):
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_STARTUP_APP_ERROR"):
            system_ui_wait_target(SYSTEM.replace("System UI isn't responding", "Other app keeps stopping"))

    def test_dump_uses_internal_shell_storage_and_checked_text_read(self):
        _, calls, _ = self.run_gate([CLEAN])
        self.assertIn(["adb", "-s", "emulator-5556", "shell", "cat",
                       "/data/local/tmp/democart-startup-ui.xml"], calls)
        self.assertFalse(any("exec-out" in c or any("/sdcard/" in a for a in c) for c in calls))

    def test_read_permission_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            def command(args, **kwargs):
                if "cat" in args:
                    raise subprocess.CalledProcessError(1, args, stderr="Permission denied")
                return "UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml"
            with self.assertRaises(subprocess.CalledProcessError):
                prepare_startup_ui(Path(temp), command)
            report = json.loads((Path(temp) / "startup/manifest.json").read_text())
            self.assertEqual(report["status"], "FAILED")
            self.assertEqual(report["system_wait_taps"], 0)

    def test_empty_ui_is_not_ready(self):
        with self.assertRaisesRegex(ValueError, "STARTUP_UI_EMPTY"):
            system_ui_wait_target("<hierarchy/>")

    def test_timed_out_wait_is_recorded_once_and_not_replayed(self):
        calls = []
        with tempfile.TemporaryDirectory() as temp:
            def command(args, **kwargs):
                calls.append((args, kwargs))
                if "dump" in args:
                    return "UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml"
                if "cat" in args:
                    return SYSTEM
                if "input" in args:
                    raise subprocess.TimeoutExpired(args, kwargs["timeout"])
                return ""
            with self.assertRaises(subprocess.TimeoutExpired):
                prepare_startup_ui(Path(temp), command)
            report = json.loads((Path(temp) / "startup/manifest.json").read_text())
            self.assertEqual(report["status"], "FAILED")
            self.assertEqual(report["system_wait_attempts"], 1)
            self.assertEqual(report["system_wait_taps"], 0)
            self.assertEqual(report["observations"][0]["recovery"]["status"], "OUTCOME_UNKNOWN")
            taps = [(args, kwargs) for args, kwargs in calls if "input" in args]
            self.assertEqual(len(taps), 1)
            self.assertEqual(taps[0][1]["timeout"], 30)


    def test_transient_empty_dump_retries_observation_without_tapping(self):
        report, calls, _ = self.run_gate([CLEAN], empty_dumps=1)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["empty_dump_attempts"], 1)
        self.assertEqual(report["system_wait_attempts"], 0)
        self.assertFalse(any("input" in call for call in calls))

    def test_three_empty_dumps_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "STARTUP_UI_DUMP_UNAVAILABLE"):
            self.run_gate([CLEAN], empty_dumps=3)


    def test_initial_settling_happens_before_any_device_call(self):
        with tempfile.TemporaryDirectory() as temp:
            clock = [0.0]
            calls = []
            def sleep(seconds):
                self.assertLessEqual(seconds, 15)
                clock[0] += seconds
            def command(args, **kwargs):
                calls.append((clock[0], args, kwargs))
                clock[0] += 1
                if "dump" in args:
                    return "UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml"
                if "cat" in args:
                    return CLEAN
                return ""
            with patch("time.monotonic", side_effect=lambda: clock[0]), patch("time.sleep", side_effect=sleep):
                result = prepare_startup_ui(Path(temp), command, budget_seconds=180, initial_idle_seconds=60)
            self.assertEqual(calls[0][0], 60)
            self.assertEqual(result["status"], "READY")
            self.assertTrue(result["idle_completed"])
            self.assertGreaterEqual(result["elapsed_seconds"], 75)
            self.assertLess(result["elapsed_seconds"], 180)
            self.assertFalse(any("input" in c[1] for c in calls))
            self.assertFalse((Path(temp) / "episodes").exists())

    def test_invalid_initial_idle_budget_rejected_without_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in (-1, 120, True, None, "60"):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "STARTUP_IDLE_BUDGET_INVALID"):
                    prepare_startup_ui(Path(temp), lambda *a, **k: self.fail("device called"), initial_idle_seconds=value)

    def run_restart_gate(self, after=CLEAN, same_pid=False, timeout=False, post_restart_empty=0,
                         absent_pids=0, pid_error=None, initial_pid_error=None):
        with tempfile.TemporaryDirectory() as temp:
            clock, calls, dumped, pids = [0.0], [], [0], [0]
            close = SYSTEM.replace("android:id/aerr_wait", "android:id/aerr_close").replace('text="Wait"', 'text="Close app"')
            def sleep(seconds):
                clock[0] += seconds
            def command(args, **kwargs):
                calls.append(args)
                clock[0] += 1
                if "dump" in args:
                    dumped[0] += 1
                    if 1 < dumped[0] <= post_restart_empty + 1:
                        return ""
                    return "UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml"
                if "cat" in args:
                    return close if dumped[0] == 1 or after == "repeat_anr" else after
                if "pidof" in args:
                    pids[0] += 1
                    if pids[0] == 1 and initial_pid_error is not None:
                        raise initial_pid_error
                    if pids[0] > 1:
                        if pid_error is not None:
                            raise pid_error
                        if pids[0] <= absent_pids + 1:
                            raise subprocess.CalledProcessError(1, args, output="", stderr="")
                    return "875" if pids[0] == 1 or same_pid else "1020"
                if "input" in args and timeout:
                    raise subprocess.TimeoutExpired(args, kwargs["timeout"])
                return ""
            error = None
            with patch("time.monotonic", side_effect=lambda: clock[0]), patch("time.sleep", side_effect=sleep):
                try:
                    result = prepare_startup_ui(Path(temp), command, budget_seconds=180,
                                                initial_idle_seconds=60, recovery="restart")
                except Exception as exc:
                    error = exc
            report = json.loads((Path(temp) / "startup/manifest.json").read_text())
            return report, calls, error

    def test_restart_targets_only_exact_android_system_dialog(self):
        close = SYSTEM.replace("android:id/aerr_wait", "android:id/aerr_close").replace('text="Wait"', 'text="Close app"')
        self.assertEqual(system_ui_restart_target(close), (540, 1332))
        for xml in (close.replace("System UI", "DemoCart"), close.replace('package="android"', 'package="fake"'), SYSTEM):
            with self.subTest(xml=xml), self.assertRaises(RuntimeError):
                system_ui_restart_target(xml)

    def test_restart_requires_changed_pid_and_clean_observations(self):
        report, calls, error = self.run_restart_gate()
        self.assertIsNone(error)
        self.assertEqual(report["status"], "READY")
        self.assertTrue(report["process_restart_verified"])
        self.assertEqual((report["system_ui_pid_before"], report["system_ui_pid_after"]), (875, 1020))
        self.assertEqual(report["system_restart_attempts"], 1)
        self.assertEqual(report["system_wait_attempts"], 0)
        self.assertEqual(len([c for c in calls if "input" in c]), 1)
        self.assertFalse(report["task_episode_started"])

    def test_restart_cannot_pass_with_unchanged_pid(self):
        report, _, error = self.run_restart_gate(same_pid=True)
        self.assertEqual(str(error), "SYSTEM_UI_RESTART_NOT_CONFIRMED")
        self.assertEqual(report["status"], "FAILED")

    def test_persistent_anr_never_repeats_close(self):
        report, calls, error = self.run_restart_gate(after="repeat_anr")
        self.assertEqual(str(error), "REPEATED_SYSTEM_UI_ANR")
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(len([c for c in calls if "input" in c]), 1)

    def test_unknown_restart_outcome_is_recorded_and_never_replayed(self):
        report, calls, error = self.run_restart_gate(timeout=True)
        self.assertIsInstance(error, subprocess.TimeoutExpired)
        self.assertEqual(report["observations"][0]["recovery"]["status"], "OUTCOME_UNKNOWN")
        self.assertEqual(report["system_restart_commands_completed"], 0)
        self.assertEqual(len([c for c in calls if "input" in c]), 1)

    def test_restarted_ui_can_initialize_past_three_empty_observations(self):
        report, calls, error = self.run_restart_gate(post_restart_empty=5)
        self.assertIsNone(error)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["empty_dump_attempts"], 5)
        self.assertTrue(report["process_restart_verified"])
        self.assertLess(report["elapsed_seconds"], 180)
        self.assertEqual(len([c for c in calls if "input" in c]), 1)

    def test_restarted_ui_permanently_empty_uses_deadline_not_another_tap(self):
        report, calls, error = self.run_restart_gate(post_restart_empty=1000)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(str(error), "SYSTEM_UI_STARTUP_TIMEOUT")
        self.assertEqual(report["status"], "FAILED")
        self.assertGreater(report["empty_dump_attempts"], 3)
        self.assertLessEqual(report["elapsed_seconds"], 180)
        self.assertFalse(report["process_restart_verified"])
        self.assertEqual(len([c for c in calls if "input" in c]), 1)

    def test_absent_replacement_pid_waits_without_repeating_restart(self):
        report, calls, error = self.run_restart_gate(absent_pids=3)
        self.assertIsNone(error)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["phase"], "READY")
        self.assertEqual(report["absent_restart_pid_attempts"], 3)
        self.assertTrue(report["process_restart_verified"])
        self.assertEqual(report["system_ui_pid_after"], 1020)
        self.assertEqual(len([c for c in calls if "input" in c]), 1)
        clean = [o for o in report["observations"] if o.get("system_ui_pid") == 1020]
        self.assertGreaterEqual(clean[-1]["elapsed_seconds"] - clean[0]["elapsed_seconds"], 15)
        self.assertLess(report["elapsed_seconds"], 180)

    def test_permanently_absent_pid_uses_shared_deadline_and_never_passes(self):
        report, calls, error = self.run_restart_gate(absent_pids=1000)
        self.assertIsInstance(error, TimeoutError)
        self.assertEqual(str(error), "SYSTEM_UI_STARTUP_TIMEOUT")
        self.assertEqual(report["status"], "FAILED")
        self.assertGreater(report["absent_restart_pid_attempts"], 3)
        self.assertFalse(report["process_restart_verified"])
        self.assertLessEqual(report["elapsed_seconds"], 180)
        self.assertEqual(len([c for c in calls if "input" in c]), 1)

    def test_missing_pre_restart_pid_is_not_tolerated(self):
        fault = subprocess.CalledProcessError(1, ["pidof"], output="", stderr="")
        report, calls, error = self.run_restart_gate(initial_pid_error=fault)
        self.assertIs(error, fault)
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["absent_restart_pid_attempts"], 0)
        self.assertFalse(any("input" in c for c in calls))

    def test_pid_transport_errors_are_not_misclassified_as_absence(self):
        faults = (
            subprocess.CalledProcessError(1, ["pidof"], output="", stderr="device offline"),
            subprocess.CalledProcessError(1, ["pidof"], output="Permission denied", stderr=""),
            subprocess.CalledProcessError(2, ["pidof"], output="", stderr=""),
            subprocess.TimeoutExpired(["pidof"], 10),
        )
        for fault in faults:
            with self.subTest(fault=fault):
                report, calls, error = self.run_restart_gate(pid_error=fault)
                self.assertIs(error, fault)
                self.assertEqual(report["status"], "FAILED")
                self.assertEqual(report["absent_restart_pid_attempts"], 0)
                self.assertEqual(len([c for c in calls if "input" in c]), 1)
