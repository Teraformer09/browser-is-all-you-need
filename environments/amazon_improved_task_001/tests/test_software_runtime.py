"""CPU-mode regression checks. No emulator, network, or model is started."""
import asyncio
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from amazon_improved_task_001 import load_environment
from amazon_improved_task_001.harness.emulator_config import runtime_options, emulator_command
from amazon_improved_task_001.harness.hosted_worker import Worker
from amazon_improved_task_001.integrations.hosted_session import HostedSession


class SoftwareRuntimeTests(unittest.TestCase):
    def test_provisioning_includes_emulator_linker_dependency_and_preflight(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts/provision_android.sh').read_text()
        self.assertIn('libxkbfile1', source)
        self.assertIn('stage emulator_executable_preflight', source)
        self.assertIn('"$ANDROID_SDK_ROOT/emulator/emulator" -version', source)


    def test_software_startup_fits_within_runtime_deadlines(self):
        settings = runtime_options('software')
        startup = sum(settings[k] for k in ('boot_timeout_seconds', 'package_ready_timeout_seconds', 'install_timeout_seconds', 'startup_ui_timeout_seconds'))
        self.assertLess(startup, settings['exchange_timeout_seconds'])
        self.assertLess(settings['exchange_timeout_seconds'], settings['episode_timeout_seconds'])
        self.assertLess(settings['episode_timeout_seconds'], settings['sandbox_timeout_minutes'] * 60)

    def test_software_waits_for_package_service_without_replaying_install(self):
        worker = Worker(self.root, acceleration='software')
        with patch.object(worker, 'command', side_effect=[
                subprocess.TimeoutExpired('adb', 10), 'package:/system/framework/framework-res.apk', 'Success']) as command, \
             patch('time.sleep'):
            worker.install_apk()
        self.assertEqual(command.call_count, 3)
        self.assertEqual(command.call_args.args[0], ['adb', '-s', 'emulator-5556', 'install', '--no-streaming', '-r', '/opt/democart/app.apk'])
        self.assertEqual(command.call_args.kwargs['timeout'], 180)

    def test_package_service_deadline_prevents_install(self):
        worker = Worker(self.root, acceleration='software')
        with patch.object(worker, 'command', return_value='') as command, \
             patch('time.monotonic', side_effect=[0, 121]):
            with self.assertRaisesRegex(RuntimeError, 'PACKAGE_MANAGER_READY_TIMEOUT'):
                worker.install_apk()
        command.assert_called_once()

    def test_kvm_install_behavior_is_unchanged(self):
        worker = Worker(self.root)
        with patch.object(worker, 'command') as command:
            worker.install_apk()
        command.assert_called_once_with(['adb', '-s', 'emulator-5556', 'install', '-r', '/opt/democart/app.apk'], timeout=60)

    def test_timed_out_commands_preserve_partial_diagnostics(self):
        worker = Worker(self.root)
        error = subprocess.TimeoutExpired(['adb'], 3, output=b'partial output', stderr=b'busy')
        with patch('subprocess.run', side_effect=error), self.assertRaises(subprocess.TimeoutExpired):
            worker.command(['adb'], timeout=3)
        record = json.loads((self.root/'runtime.log').read_text())
        self.assertEqual((record['returncode'], record['error'], record['timeout_seconds']), (None, 'COMMAND_TIMEOUT', 3))
        self.assertEqual((record['stdout'], record['stderr']), ('partial output', 'busy'))

    def test_software_uses_lean_api33_without_changing_kvm_image(self):
        self.assertEqual(runtime_options('software')['system_image'], 'system-images;android-33;default;x86_64')
        self.assertEqual(runtime_options('kvm')['system_image'], 'system-images;android-33;google_apis;x86_64')
        source = (Path(__file__).resolve().parents[1] / 'scripts/provision_android.sh').read_text()
        self.assertIn("'system-images;android-33;default;x86_64'", source)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_default_keeps_hardware_mode(self):
        settings = runtime_options()
        self.assertTrue(settings['requires_kvm'])
        self.assertEqual((settings['accel'], settings['cores'], settings['boot_timeout_seconds']), ('on', 4, 240))

    def test_software_mode_is_explicit_and_bounded(self):
        settings = runtime_options('software')
        self.assertFalse(settings['requires_kvm'])
        self.assertEqual((settings['accel'], settings['cores'], settings['boot_timeout_seconds']), ('off', 1, 600))
        self.assertGreater(settings['exchange_timeout_seconds'], settings['boot_timeout_seconds'])
        command = emulator_command('/sdk/emulator', 'software')
        self.assertEqual(command[command.index('-accel') + 1], 'off')
        self.assertEqual(command[command.index('-gpu') + 1], 'swiftshader')

    def test_bad_modes_rejected_before_resources(self):
        for mode in ('auto', '', None, True, [], 'off; echo command'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                runtime_options(mode)

    def test_kvm_still_fails_closed(self):
        worker = Worker(self.root)
        with patch('pathlib.Path.is_char_device', return_value=False), patch.object(worker, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'KVM_UNAVAILABLE'):
                worker.boot()
            command.assert_not_called()

    def test_software_skips_kvm_but_requires_actual_emulator(self):
        worker = Worker(self.root, acceleration='software')
        with patch('pathlib.Path.is_char_device', return_value=False), patch.object(worker, 'command', side_effect=RuntimeError('stop-before-boot')) as command:
            with self.assertRaisesRegex(RuntimeError, 'stop-before-boot'):
                worker.boot()
            self.assertEqual(command.call_args.args[0][-1], '-version')
        self.assertIn('software', (self.root/'runtime-config.json').read_text())

    def test_hosted_session_propagates_mode(self):
        client = Mock()
        client.create.return_value = SimpleNamespace(id='offline-sandbox')
        client.start_background_job.return_value = SimpleNamespace(job_id='offline-job')
        session = HostedSession(self.root, client=client, acceleration='software')
        with patch.object(session, 'call', return_value={}):
            session.start()
        self.assertIn('--acceleration software', client.start_background_job.call_args.args[1])
        self.assertEqual(session.info['emulator_runtime']['acceleration'], 'software')

    def test_hosted_loader_does_not_run_or_change_rubric(self):
        with patch('amazon_improved_task_001.integrations.hosted_env.HostedSession') as session:
            env = load_environment(acceleration='software', live_viewer=False)
            self.assertEqual(env.rubric_profile, 'peach_action_budget_v1')
            self.assertEqual(env.acceleration, 'software')
            with self.assertRaisesRegex(RuntimeError, 'allow_eval'):
                asyncio.run(env.setup_state({'trajectory_id': 'no-paid-run'}))
            session.assert_not_called()
