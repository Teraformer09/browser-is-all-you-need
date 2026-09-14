"""Offline synthetic tests. No device, model call, or Prime resource is created."""
import copy
import json
from itertools import product
from unittest.mock import patch

import pytest

from fixture_device import FixtureDevice
from amazon_improved_task_001.harness.peach_episode import PeachEpisode
from amazon_improved_task_001.harness.hosted_worker import validate_request, Worker
from amazon_improved_task_001.verification import action_budget as b
from amazon_improved_task_001.verification.contracts import Unassessable
from amazon_improved_task_001.verification.peach import task_spec


@pytest.fixture
def episode(tmp_path):
    with patch('amazon_improved_task_001.harness.peach_episode.PeachDevice', FixtureDevice):
        env = PeachEpisode('FAKE', 'FAKE.apk', tmp_path, rubric_profile=b.PROFILE)
    env.reset()
    return env


def act(env, kind, target=None, text=None):
    a = {'type': kind}
    if target is not None:
        a['element_id'] = target
    if text is not None:
        a['text'] = text
    return env.step(json.dumps(a))


def complete(env, count=3, cart=True, finish=True):
    for item in task_spec()['expected_items'][:count]:
        act(env, 'type_text', 'search_input', item['query'])
        act(env, 'tap_element', 'search_button')
        act(env, 'tap_element', 'add_' + item['sku'])
    if cart:
        act(env, 'tap_element', 'cart_button')
    if finish:
        act(env, 'finish')
    return env


def metrics(env, tokens=165, seconds=13):
    rows = [{'request_index': i+1, 'action_step': i+1, 'raw_response': t['raw_response'],
             'completion_tokens': tokens if i == 0 else 0, 'elapsed_seconds': seconds if i == 0 else 0}
            for i, t in enumerate(env.transitions)]
    env.set_model_evidence({'schema_version': 1, 'episode_id': env.episode,
                           'source': 'host_controller', 'requests': rows})


def terminal(env):
    env.context['actor_stopped'] = True
    return b.evaluate(env.context)


def test_success_has_nine_correctness_and_all_five_optimizer_results(episode):
    complete(episode)
    metrics(episode)
    verdict = episode.finalize()
    assert verdict['status'] == 'PASS', verdict['reason_codes']
    assert len(verdict['policies']) == 3
    assert sum(len(p['correctness_results']) for p in verdict['policies']) == 9
    assert [o['status'] for o in verdict['shared_optimizers']] == ['PASS'] * 5
    assert len(list((episode.root / 'policy_receipts').glob('*.json'))) == 3
    assert len({tuple(p['optimizer_refs']) for p in verdict['policies']}) == 1
    assert all(p['support_score'] == 1 and p['reward'] == 1 for p in verdict['policies'])


@pytest.mark.parametrize('tokens,seconds,expected,passed', [(165,13,'PASS',5), (165,13.00001,'PASS',4),
    (166,13,'PASS',4), (166,13.00001,'FAIL',3), (0,0,'PASS',5)])
def test_inclusive_boundaries(episode, tokens, seconds, expected, passed):
    complete(episode)
    metrics(episode, tokens, seconds)
    verdict = terminal(episode)
    assert verdict['status'] == expected
    assert all(p['passed_optimizers'] == passed for p in verdict['policies'])


def test_budget_only_counts_actor_not_low_level_adb(episode):
    complete(episode)
    metrics(episode)
    results = b.optimizer_results(episode.context, True)
    assert [r['actual'] for r in results[:3]] == [3,7,11]
    assert len(episode.context['adb_trace']) > 11


@pytest.mark.parametrize('index,value', [(0,4),(1,8),(2,12)])
def test_action_count_cap(index, value):
    key = ('type_text', 'tap_element', 'wait')[index]
    c = {'transitions': [{'action': {'type': key}} for _ in range(value)]}
    results = b.optimizer_results(c, True)
    assert results[index]['status'] == 'FAIL'
    assert len(results) == 5


def test_exhaustive_vote_scoring():
    checks = [b.result(str(i),'PASS','TEST') for i in range(3)]
    for votes in product(('PASS','FAIL','INVALID'), repeat=5):
        rows = [b.result('O'+str(i+1), s, 'TEST') for i,s in enumerate(votes)]
        r = b.score_policy('ITEM.DC001', checks, rows)
        expected = 'INVALID' if votes == ('INVALID',)*5 else 'PASS' if votes.count('PASS') >= 4 else 'FAIL'
        assert r['status'] == expected
        assert r['support_score'] == (5 + votes.count('PASS')) / 10


@pytest.mark.parametrize('baseline', ['FAIL','INVALID'])
def test_baseline_never_awarded_for_missing_success(baseline):
    checks = [b.result(str(i), baseline if i == 0 else 'PASS','TEST') for i in range(3)]
    opts = [b.result('O'+str(i+1),'PASS','TEST') for i in range(5)]
    r = b.score_policy('ITEM.DC001', checks, opts)
    assert r['status'] == baseline and r['baseline_reward'] == 0 and r['support_score'] == 0


def test_text_only_is_not_search_or_cart_credit(episode):
    act(episode, 'type_text', 'search_input', 'wireless headphones')
    r = terminal(episode)['policies'][0]
    assert [c['status'] for c in r['correctness_results']] == ['PASS','FAIL','FAIL']
    assert r['baseline_reward'] == 0


def test_search_only_is_not_cart_credit(episode):
    act(episode, 'type_text', 'search_input', 'wireless headphones')
    act(episode, 'tap_element', 'search_button')
    assert [c['status'] for c in terminal(episode)['policies'][0]['correctness_results']] == ['PASS','PASS','FAIL']


def test_wrong_search_then_add_does_not_establish_chain(episode):
    act(episode, 'type_text', 'search_input', 'laptop backpack')
    act(episode, 'tap_element', 'search_button')
    act(episode, 'tap_element', 'add_DC001')
    r = terminal(episode)['policies'][0]
    assert r['status'] == 'FAIL' and r['baseline_reward'] == 0


def test_final_cart_gate_remains_required(episode):
    complete(episode, cart=False, finish=False)
    metrics(episode)
    verdict = terminal(episode)
    assert verdict['status'] == 'FAIL'
    assert next(g for g in verdict['strict_checks'] if g['check_id']=='exact_outcome')['status']=='FAIL'


def test_duplicate_quantity_fails_even_with_action_chain(episode):
    complete(episode, count=1, cart=False, finish=False)
    act(episode, 'tap_element', 'add_DC001')
    assert terminal(episode)['policies'][0]['correctness_results'][2]['status'] == 'FAIL'


def test_every_check_executes_without_short_circuit(episode):
    complete(episode)
    metrics(episode)
    seen = []
    def tracked(name, fn):
        def call(*args):
            seen.append((args[2]['sku'], name))
            return fn(*args)
        return call
    with patch.dict(b.CHECKS, {name:tracked(name, fn) for name,fn in b.CHECKS.items()}):
        assert terminal(episode)['status'] == 'PASS'
    assert len(seen) == len(set(seen)) == 9


@pytest.mark.parametrize('value', [None, -1, float('nan'), float('inf'), True, '165'])
def test_unreadable_token_usage_not_zero(episode, value):
    complete(episode)
    metrics(episode)
    episode.context['model_evidence']['requests'][0]['completion_tokens'] = value
    results = b.optimizer_results(episode.context, True)
    assert results[3]['status'] == 'INVALID' and results[3]['actual'] is None


def test_wrong_raw_response_binding_invalidates_model_metrics(episode):
    complete(episode)
    metrics(episode)
    episode.context['model_evidence']['requests'][0]['raw_response'] = '{}'
    assert [r['status'] for r in b.optimizer_results(episode.context,True)[3:]] == ['INVALID','INVALID']


def test_empty_response_retries_count_in_tokens_and_time(episode):
    complete(episode)
    metrics(episode)
    rows = episode.context['model_evidence']['requests']
    rows.insert(0, {'action_step':None,'raw_response':'','completion_tokens':200,'elapsed_seconds':2})
    for i,r in enumerate(rows):
        r['request_index'] = i+1
    assert [r['actual'] for r in b.optimizer_results(episode.context,True)[3:]] == [365,15]


def test_stale_missing_or_corrupt_frame_evidence_is_invalid(episode):
    complete(episode)
    metrics(episode)
    (episode.root/'frames/001/screen.png').write_bytes(b'corrupt')
    assert terminal(episode)['status'] == 'INVALID'


def test_invalid_finish_does_not_end_but_remains_failed_action(episode):
    act(episode,'finish')
    assert episode.done is False
    complete(episode)
    metrics(episode)
    assert terminal(episode)['status'] == 'FAIL'


def test_intermediate_status_is_pending(episode):
    complete(episode,count=1,cart=False,finish=False)
    assert b.evaluate(episode.context)['status'] == 'PENDING'
    assert all(p['status']=='PENDING' and p['reward'] is None for p in b.evaluate(episode.context)['policies'])


def test_worker_accepts_controller_metrics_not_actor_tool():
    validate_request({'sequence':3,'operation':'model_evidence','model_evidence':{}},3)
    with pytest.raises(ValueError):
        validate_request({'sequence':3,'operation':'model_evidence','model_evidence':[]},3)
    with pytest.raises(ValueError):
        validate_request({'sequence':3,'operation':'model_evidence','model_evidence':{},'action':'{}'},3)


def test_usage_cannot_change_after_finalization(episode):
    complete(episode)
    metrics(episode)
    episode.finalize()
    with pytest.raises(RuntimeError):
        metrics(episode,0,0)
