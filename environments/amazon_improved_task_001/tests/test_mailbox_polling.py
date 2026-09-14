"""No-network regression tests for ambiguous RPC completion and cleanup."""
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from amazon_improved_task_001.harness.hosted_worker import exchange, write_json
from amazon_improved_task_001.integrations.hosted_session import HostedSession


class MailboxPollingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = HostedSession(self.root, client=Mock())
        self.session.sandbox_id = 'test-vm'

    def receipt(self, value):
        return SimpleNamespace(exit_code=0, stdout=json.dumps(value), stderr='')

    def test_poll_publishes_request_once_and_returns_pending(self):
        request = {'sequence': 0, 'operation': 'reset'}
        write_json(self.root / 'request-000.incoming', request)
        for _ in range(2):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                exchange(self.root, 0, poll=True)
            self.assertEqual(json.loads(out.getvalue()), {'pending': True, 'sequence': 0})
        self.assertEqual(json.loads((self.root / 'request-000.json').read_text()), request)

    def test_conflicting_poll_still_rejected(self):
        write_json(self.root / 'request-000.json', {'sequence': 0, 'operation': 'reset'})
        write_json(self.root / 'request-000.incoming', {'sequence': 0, 'operation': 'finalize'})
        with self.assertRaisesRegex(RuntimeError, 'Conflicting retry'):
            exchange(self.root, 0, poll=True)

    def test_transient_rpc_then_pending_then_response_no_reupload(self):
        s = self.session
        s.client.execute_command.side_effect = [TimeoutError('transport'), self.receipt({'pending': True, 'sequence': 0}), self.receipt({'path': 'receipt'})]
        with patch.object(s, 'download', return_value=b'{"sequence":0,"ok":true,"result":{"done":false}}'), patch('amazon_improved_task_001.integrations.hosted_session.time.sleep'):
            self.assertEqual(s.call('reset'), {'done': False})
        s.client.upload_file.assert_called_once()
        self.assertEqual(s.sequence, 1)
        self.assertIsNone(s.pending_request)
        self.assertEqual(len(s.info['transport_recovery']), 1)
        for call in s.client.execute_command.call_args_list:
            self.assertIn('--poll', call.args[1])
            self.assertLessEqual(call.kwargs['timeout'], 30)

    def test_exhausted_transport_retains_request_and_blocks_next_action(self):
        s = self.session
        s.client.execute_command.side_effect = TimeoutError('transport')
        with patch('amazon_improved_task_001.integrations.hosted_session.time.sleep'), self.assertRaises(TimeoutError):
            s.call('reset')
        self.assertEqual(s.client.execute_command.call_count, 3)
        with self.assertRaisesRegex(RuntimeError, 'Unresolved'):
            s.call('finalize')
        s.client.upload_file.assert_called_once()
        self.assertEqual(s.pending_request['operation'], 'reset')

    def test_cleanup_reconciles_before_new_finalize_sequence(self):
        s = self.session
        s.started = True
        s.pending_request = {'sequence': 0, 'operation': 'reset'}
        s.client.execute_command.side_effect = [self.receipt({}), self.receipt({})]
        responses = [b'{"sequence":0,"ok":true,"result":{}}', b'{"sequence":1,"ok":true,"result":{"verdict":{"status":"PASS","reward":1},"archive":{}}}', b'archive']
        with patch.object(s, 'download', side_effect=responses), patch('amazon_improved_task_001.integrations.hosted_session.archive_payload', return_value={}):
            verdict = s.finish('original timeout')
        self.assertEqual(verdict['status'], 'INVALID')
        self.assertTrue(s.info['evidence_export_verified'])
        self.assertEqual(s.sequence, 2)
        self.assertEqual(json.loads((s.root/'request-001.json').read_text())['operation'], 'finalize')
        self.assertFalse((s.root/'request-000.json').exists())
        s.client.delete.assert_called_once()

    def test_unrecoverable_pending_never_sends_conflicting_finalize(self):
        s = self.session
        s.started = True
        s.pending_request = {'sequence': 0, 'operation': 'reset'}
        s.client.execute_command.side_effect = TimeoutError('transport')
        with patch('amazon_improved_task_001.integrations.hosted_session.time.sleep'):
            self.assertEqual(s.finish()['status'], 'INVALID')
        s.client.upload_file.assert_not_called()
        s.client.delete.assert_called_once()

    def test_wrong_pending_identity_is_rejected(self):
        s = self.session
        s.client.execute_command.return_value = self.receipt({'pending': True, 'sequence': 9})
        with self.assertRaisesRegex(ValueError, 'Malformed pending'):
            s.call('reset')
        self.assertEqual(s.sequence, 0)

    def test_deadline_is_bounded(self):
        s = self.session
        s.pending_request = {'sequence': 0, 'operation': 'reset'}
        with self.assertRaises(TimeoutError):
            s.receive_pending(0)
        s.client.execute_command.assert_not_called()
        self.assertIsNotNone(s.pending_request)

    def test_poll_awaits_upload_instead_of_crashing(self):
        # Regression: the finalize mailbox race deleted request-012.incoming
        # before exchange ran; a missing request must report pending, not crash.
        with contextlib.redirect_stdout(io.StringIO()) as out:
            exchange(self.root, 12, poll=True)
        self.assertEqual(json.loads(out.getvalue()),
                         {'pending': True, 'sequence': 12, 'delivery': 'awaiting_upload'})

    def test_blocking_exchange_waits_for_delivery_then_stages(self):
        import threading
        request = {'sequence': 0, 'operation': 'reset'}
        def deliver():
            time.sleep(0.3)
            write_json(self.root / 'request-000.incoming', request)
        threading.Thread(target=deliver, daemon=True).start()
        with patch('amazon_improved_task_001.harness.hosted_worker.runtime_options') as options:
            options.return_value = {'exchange_timeout_seconds': 2}
            with self.assertRaisesRegex(TimeoutError, 'Worker response deadline'):
                exchange(self.root, 0)
        # No crash on the missing upload: delivery was awaited, then staged once.
        self.assertEqual(json.loads((self.root / 'request-000.json').read_text()), request)

    def test_blocking_exchange_times_out_without_delivery(self):
        with patch('amazon_improved_task_001.harness.hosted_worker.runtime_options') as options:
            options.return_value = {'exchange_timeout_seconds': 0.2}
            with self.assertRaisesRegex(TimeoutError, 'Request delivery deadline'):
                exchange(self.root, 0)
