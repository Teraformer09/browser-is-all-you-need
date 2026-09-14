"""Synthetic evidence only: no Android, model, Prime API, or billed evaluation."""
import copy
import hashlib
import json
import sqlite3
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element, SubElement, tostring

from amazon_improved_task_001.harness.peach import PACKAGE, PROFILE, ui_nodes
from amazon_improved_task_001.harness.peach_episode import PeachEpisode
from amazon_improved_task_001.verification.peach import snapshot, task_spec
from amazon_improved_task_001.verification.strict import cart_lineage, evaluate


def sha(data):
    return hashlib.sha256(data).hexdigest()


def png():
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1080, 1920, 8, 0, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress((b'\x00' + b'\xff' * 1080) * 1920)) + chunk(b'IEND', b''))


class FixtureDevice:
    """Small deterministic fake producing real SQLite/XML/PNG files, not a task agent."""
    def __init__(self, *args):
        self.trace, self.phase = [], 'setup'
        self.products = [dict(id=i + 1, sku=p['sku'], name=p['name'], category='Electronics',
                             price_paise=p['unit_price_paise']) for i, p in enumerate(task_spec()['expected_items'])]

    def installed(self, apk):
        return dict(package=PACKAGE, sha256='a' * 64, expected_sha256='a' * 64)

    def start(self, episode):
        self.episode = episode
        self.tables = dict(products=self.products, cart=[], search_history=[], eval_events=[],
                          eval_session=[dict(singleton=1, episode_id=episode, page='home', draft='', query='')])
        self.event('reset', dict(episode_id=episode))

    def event(self, kind, payload):
        self.tables['eval_events'].append(dict(sequence=len(self.tables['eval_events']), kind=kind, payload=json.dumps(payload)))

    def viewport(self):
        self.event('viewport', {k: self.tables['eval_session'][0][k] for k in ('page', 'draft', 'query')})

    def xml(self):
        root = Element('hierarchy')
        def node(resource='', description='', text='', y=10, edit=False):
            SubElement(root, 'node', {'package': PACKAGE, 'resource-id': PACKAGE + ':id/' + resource,
                'content-desc': description, 'text': text, 'enabled': 'true', 'clickable': 'true',
                'class': 'android.widget.EditText' if edit else 'android.widget.Button',
                'bounds': f'[10,{y}][900,{y+60}]'})
        node('etSearchBox', text=self.tables['eval_session'][0]['draft'], edit=True)
        node('btnSearch', y=90)
        node(description='Cart tab', y=170)
        for i, p in enumerate(self.products):
            node(description='Add ' + p['name'] + ' to cart', y=250+i*80)
        if self.tables['eval_session'][0]['page'] == 'cart':
            state = snapshot(self.tables, self.episode)
            node(text=f"Subtotal ({state['cart_count']} items): ₹{state['subtotal_paise']//100:,}", y=600)
        return tostring(root)

    def trace_entry(self, args, data=b''):
        self.trace.append(dict(args=args, phase=self.phase, returncode=0, bytes=len(data), sha256=sha(data)))

    def ui(self):
        raw, remote = self.xml(), '/sdcard/peach-ui-' + 'b'*32 + '.xml'
        self.trace_entry(['shell', 'uiautomator', 'dump', remote])
        self.trace_entry(['exec-out', 'cat', remote], raw)
        self.trace_entry(['shell', 'rm', '-f', remote])
        return raw

    def execute(self, action, target):
        import shlex
        kind = action['type']
        session = self.tables['eval_session'][0]
        if kind in {'tap_element', 'type_text'}:
            l, t, r, b = target['bounds']
            self.trace_entry(['shell', 'input', 'tap', str((l+r)//2), str((t+b)//2)])
        if kind == 'type_text':
            self.trace_entry(['shell', 'input', 'keycombination', '113', '29'])
            self.trace_entry(['shell', 'input', 'keyevent', 'KEYCODE_DEL'])
            if action['text']:
                self.trace_entry(['shell', 'input', 'text', shlex.quote(action['text'].replace(' ', '%s'))])
            self.trace_entry(['shell', 'input', 'keyevent', 'KEYCODE_BACK'])
            session['draft'] = action['text']
            self.viewport()
        elif action.get('element_id') == 'search_button':
            session.update(page='results', query=session['draft'].strip())
            self.viewport()
            self.event('search', dict(query=session['query']))
        elif action.get('element_id', '').startswith('add_'):
            product = next(p for p in self.products if p['sku'] == action['element_id'][4:])
            row = next((r for r in self.tables['cart'] if r['product_id'] == product['id']), None)
            if row is None:
                row = dict(product_id=product['id'], qty=0)
                self.tables['cart'].append(row)
                self.tables['cart'].sort(key=lambda r: r['product_id'])
            row['qty'] += 1
            self.event('add', dict(product_id=product['id'], quantity_after=row['qty']))
        elif action.get('element_id') == 'cart_button':
            session['page'] = 'cart'
            self.viewport()

    def capture(self, root, index, episode):
        self.phase = 'observation'
        tables = copy.deepcopy(self.tables)
        with sqlite3.connect(':memory:') as db:
            for name, rows in tables.items():
                columns = list(rows[0]) if rows else {'cart':['product_id','qty'], 'search_history':['query','searched_at']}[name]
                db.execute('CREATE TABLE ' + name + '(' + ','.join(columns) + ')')
                for row in rows:
                    db.execute('INSERT INTO ' + name + ' VALUES (' + ','.join('?' for _ in columns) + ')', list(row.values()))
            db.commit()
            database = db.serialize()
        xml = self.xml()
        values = dict.fromkeys(('runtime_before.json', 'runtime.json', 'persisted_state.json'), json.dumps(tables).encode())
        values.update({'database.sqlite':database, 'ui.xml':xml, 'screen.png':png()})
        directory = root / 'frames' / f'{index:03d}'
        directory.mkdir(parents=True)
        artifacts = {}
        for name, raw in values.items():
            path = directory / name
            path.write_bytes(raw)
            artifacts[name] = dict(path=str(path.relative_to(root)), sha256=sha(raw))
        return dict(index=index, episode_id=episode, stable=True, profile=PROFILE,
                    tables=tables, artifacts=artifacts, ui=ui_nodes(xml, self.products))


class StrictTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch('amazon_improved_task_001.harness.peach_episode.PeachDevice', FixtureDevice):
            self.episode = PeachEpisode('FAKE', 'FAKE.apk', self.temp.name, rubric_profile='peach_strict_v1')
        self.episode.reset()

    def action(self, kind, target=None, text=None):
        value = dict(type=kind)
        if target is not None: value['element_id'] = target
        if text is not None: value['text'] = text
        return self.episode.step(json.dumps(value))

    def completed(self):
        for product in task_spec()['expected_items']:
            self.action('type_text', 'search_input', product['query'])
            self.action('tap_element', 'search_button')
            self.action('tap_element', 'add_' + product['sku'])
        self.action('tap_element', 'cart_button')
        self.action('finish')
        return self.episode.context

    def test_complete_fixture_passes_all_strict_checks(self):
        result = evaluate(self.completed())
        self.assertEqual(result['status'], 'PASS', result['reason_codes'])
        self.assertEqual(len(result['strict_checks']), 6)
        self.assertEqual(len(result['policies']), 15)
        self.assertEqual(sum(len(p['verifier_results']) for p in result['policies']), 75)
        self.assertEqual(result['policy_vote_role'], 'diagnostic_only')

    def test_unfinished_but_readable_is_failure(self):
        self.assertEqual(self.episode.finalize()['status'], 'FAIL')

    def test_checkpoints_remain_pending_not_terminal_failures(self):
        self.action('type_text', 'search_input', 'headphones')
        point = self.episode.history[-1]
        self.assertEqual(point['episode_status'], 'PENDING')
        self.assertIsNone(point['episode_reward'])
        self.assertEqual(len(point['strict_checks']), 6)

    def test_forged_passing_legacy_votes_cannot_override_empty_cart(self):
        with patch('amazon_improved_task_001.verification.strict.legacy_evaluate', return_value={'status':'PASS','policies':[]}):
            self.assertEqual(evaluate(self.episode.context)['status'], 'FAIL')

    def test_missing_dispatch_is_invalid_not_pass(self):
        context = self.completed()
        context['transitions'][0]['dispatch_artifact'] = None
        result = evaluate(context)
        self.assertEqual(result['status'], 'INVALID', result['reason_codes'])

    def test_modified_dispatch_metadata_is_invalid(self):
        context = self.completed()
        context['transitions'][0]['dispatch_ui'][0]['bounds'][0] += 1
        self.assertEqual(evaluate(context)['status'], 'INVALID')

    def test_modified_adb_coordinates_is_invalid(self):
        context = self.completed()
        tap = next(e for e in context['adb_trace'] if e['args'][:3] == ['shell','input','tap'])
        tap['args'][-1] = '9999'
        self.assertEqual(evaluate(context)['status'], 'INVALID')

    def test_missing_or_modified_required_files_is_invalid(self):
        context = self.completed()
        path = self.episode.root / 'frames/011/screen.png'
        path.write_bytes(b'corrupt')
        self.assertEqual(evaluate(context)['status'], 'INVALID')

    def test_stale_episode_is_invalid(self):
        context = self.completed()
        context['frames'][0]['episode_id'] = 'peach_' + 'c'*32
        self.assertEqual(evaluate(context)['status'], 'INVALID')

    def test_malformed_actions_fail_without_rollout_crash(self):
        for raw in ('[]', '42', 'null', 'not JSON'):
            self.episode.step(raw)
        self.completed()
        result = self.episode.finalize()
        self.assertEqual(result['status'], 'FAIL', result['reason_codes'])
        self.assertEqual(len(self.episode.transitions), 15)

    def test_premature_finish_fails_but_allows_continuation(self):
        self.action('finish')
        self.assertFalse(self.episode.done)
        self.completed()
        self.assertEqual(self.episode.finalize()['status'], 'FAIL')

    def test_missing_task_is_invalid(self):
        self.episode.context['task'] = {}
        self.assertEqual(evaluate(self.episode.context)['status'], 'INVALID')

    def test_state_disagreement_is_invalid(self):
        context = self.completed()
        context['frames'][-1]['tables']['cart'][0]['qty'] = 2
        self.assertEqual(evaluate(context)['status'], 'INVALID')

    def test_removed_search_add_cannot_launder_unsearched_readd(self):
        tables = copy.deepcopy(self.completed()['frames'][-1]['tables'])
        def event(kind, data):
            tables['eval_events'].append(dict(sequence=len(tables['eval_events']), kind=kind, payload=json.dumps(data)))
        event('remove', dict(product_id=1, quantity_after=0))
        event('viewport', dict(page='home', draft='', query=''))
        event('add', dict(product_id=1, quantity_after=1))
        self.assertFalse(cart_lineage(tables, task_spec()))

    def test_quantity_correction_keeps_current_acquisition_interval(self):
        tables = copy.deepcopy(self.completed()['frames'][-1]['tables'])
        for kind, quantity in [('add', 2), ('decrease', 1)]:
            tables['eval_events'].append(dict(sequence=len(tables['eval_events']), kind=kind,
                payload=json.dumps(dict(product_id=1, quantity_after=quantity))))
        self.assertTrue(cart_lineage(tables, task_spec()))

    def test_unbound_low_level_action_invalidates_evidence(self):
        context = self.completed()
        context["adb_trace"].append(dict(phase="action", args=["shell","input","tap","1","1"], returncode=0))
        self.assertEqual(evaluate(context)["status"], "INVALID")

    def test_nonobject_context_is_controlled_invalid(self):
        for value in (None, [], 42):
            self.assertEqual(evaluate(value)["status"], "INVALID")

    def test_local_legacy_profile_remains_explicit_and_unchanged(self):
        with patch('amazon_improved_task_001.harness.peach_episode.PeachDevice', FixtureDevice):
            legacy = PeachEpisode('FAKE', 'FAKE.apk', self.temp.name)
        self.assertEqual(legacy.rubric_profile, 'legacy_v1')


if __name__ == '__main__':
    unittest.main()
