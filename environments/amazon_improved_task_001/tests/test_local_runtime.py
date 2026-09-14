"""Offline launch/cleanup safety tests; no Android, model or Prime resources."""
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from amazon_improved_task_001.harness.local_runtime import LocalRuntime, OUTPUT, require_free_ports, require_local_output, stop_owned
from amazon_improved_task_001.integrations.live_viewer import LiveViewer


class LocalRuntimeTests(unittest.TestCase):
    def test_local_readiness_viewer_is_explicit(self):
        viewer = LiveViewer(Mock(), public_readonly=True, local_readiness=True)
        status = viewer.status()
        self.assertTrue(status["local_readiness"])
        self.assertFalse(status["interactive"])
        self.assertTrue(status["public_readonly"])
        self.assertTrue(status["evaluation_control_disabled"])

    def test_existing_hosted_viewer_context_unchanged(self):
        viewer = LiveViewer(Mock(), public_readonly=True)
        self.assertFalse(viewer.status()["local_readiness"])

    def test_local_readiness_context_rejects_input_and_malformed_flag(self):
        for kwargs in ({"local_readiness": "yes"},
                       {"local_readiness": True, "interactive": True, "control": Mock()},
                       {"local_readiness": True, "control": Mock()}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                LiveViewer(Mock(), **kwargs)

    def test_output_is_task_owned(self):
        self.assertEqual(require_local_output(OUTPUT/'a'),(OUTPUT/'a').resolve())
        for path in ('/', '/data/Tirtha', '/tmp', OUTPUT/'../../other'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                require_local_output(path)

    def test_occupied_port_is_not_replaced(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0))
            with self.assertRaisesRegex(RuntimeError,'occupied'):
                require_free_ports((occupied.getsockname()[1],))
            self.assertGreater(occupied.fileno(),0)

    def test_free_port_probe_releases_socket(self):
        with socket.socket() as available:
            available.bind(('127.0.0.1',0))
            port=available.getsockname()[1]
        require_free_ports((port,))
        with socket.socket() as again:
            again.bind(('127.0.0.1',port))

    def test_stopped_child_not_signalled(self):
        process=Mock()
        process.poll.return_value=0
        stop_owned(process)
        process.terminate.assert_not_called()
        stop_owned(None)

    def test_own_child_stopped(self):
        process=Mock()
        process.poll.return_value=None
        stop_owned(process)
        process.terminate.assert_called_once_with()
        process.kill.assert_not_called()

    def test_hung_child_killed_after_grace(self):
        process=Mock()
        process.poll.return_value=None
        process.wait.side_effect=[subprocess.TimeoutExpired('owned',15),0]
        stop_owned(process)
        process.kill.assert_called_once_with()

    def make_runtime(self):
        with patch('pathlib.Path.is_file',return_value=True), patch('os.access',return_value=True):
            return LocalRuntime('/opt/sdk','/opt/java','/opt/ffmpeg')

    def test_construction_creates_nothing_and_is_not_eval(self):
        with patch('subprocess.Popen') as popen, patch('pathlib.Path.mkdir') as mkdir:
            runtime=self.make_runtime()
        popen.assert_not_called()
        mkdir.assert_not_called()
        self.assertFalse(runtime.report['evaluation'])
        self.assertFalse(runtime.report['prime_hosted'])
        self.assertEqual(runtime.report['model_calls'],0)
        self.assertIsNone(runtime.report['reward'])

    def test_missing_kvm_fails_before_creating_runtime(self):
        runtime=self.make_runtime()
        with patch('amazon_improved_task_001.harness.local_runtime.require_free_ports'), \
             patch('pathlib.Path.is_char_device',return_value=False), patch('pathlib.Path.mkdir') as mkdir:
            with self.assertRaisesRegex(RuntimeError,'no software'):
                runtime.configure()
        mkdir.assert_not_called()

    def test_missing_tool_is_an_error(self):
        with patch('pathlib.Path.is_file',return_value=False), self.assertRaisesRegex(ValueError,'executable'):
            LocalRuntime('/missing/sdk','/missing/java','/missing/ffmpeg')

    def test_environment_restored_after_close(self):
        runtime=self.make_runtime()
        with patch.dict(os.environ,{'DEMOCART_TEST_EXISTING':'during'},clear=False):
            runtime.previous_env={'DEMOCART_TEST_EXISTING':'before','DEMOCART_TEST_NEW':None}
            os.environ['DEMOCART_TEST_NEW']='during'
            runtime.close()
            self.assertEqual(os.environ['DEMOCART_TEST_EXISTING'],'before')
            self.assertNotIn('DEMOCART_TEST_NEW',os.environ)

    def test_cleanup_does_not_delete_unowned_directory(self):
        runtime=self.make_runtime()
        with tempfile.TemporaryDirectory() as path:
            runtime.root=Path(path)
            runtime.work=runtime.root/'user-data'
            runtime.work.mkdir()
            runtime.close()
            self.assertTrue(runtime.work.is_dir())

    def test_owned_temporary_data_removed_but_receipts_retained(self):
        runtime=self.make_runtime()
        with tempfile.TemporaryDirectory() as path:
            runtime.root=Path(path)
            runtime.work=runtime.root/'runtime.test'
            runtime.work.mkdir()
            runtime.close()
            self.assertFalse(runtime.work.exists())
            self.assertTrue((runtime.root/'readiness.json').is_file())

    def test_modern_android_paths_do_not_conflict_with_legacy_roots(self):
        runtime=self.make_runtime()
        with tempfile.TemporaryDirectory() as path, \
             patch('amazon_improved_task_001.harness.local_runtime.require_free_ports'), \
             patch('pathlib.Path.is_char_device',return_value=True), patch('os.access',return_value=True), \
             patch.dict(os.environ,{'ANDROID_SDK_HOME':'old','ANDROID_PREFS_ROOT':'old'}):
            runtime.output=Path(path)
            try:
                runtime.configure()
                self.assertNotIn('ANDROID_SDK_HOME',os.environ)
                self.assertNotIn('ANDROID_PREFS_ROOT',os.environ)
                self.assertEqual(os.environ['ANDROID_HOME'],str(runtime.sdk))
                self.assertEqual(os.environ['ANDROID_SDK_ROOT'],str(runtime.sdk))
                self.assertTrue(Path(os.environ['ANDROID_USER_HOME']).is_dir())
            finally:
                runtime.close()
            self.assertEqual(os.environ['ANDROID_SDK_HOME'],'old')
            self.assertEqual(os.environ['ANDROID_PREFS_ROOT'],'old')


if __name__=='__main__':
    unittest.main()
