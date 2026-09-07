"""Synthetic, offline policy fixtures. No emulator, model, Prime call or published result."""
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import escape
from amazon_cart_001.harness.actions import PACKAGE, TARGETS, decode, schema_error, permission_error
from amazon_cart_001.harness.evidence import digest, nodes
from amazon_cart_001.specs import task_path
from amazon_cart_001.verification.registry import evaluate, load_registry, VERIFIERS
from amazon_cart_001.verification.evidence_readers import replay_operations
from amazon_cart_001.verification.scoring import score_policy, REWARDS
from amazon_cart_001.verification.task_checks import cart_complete

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = json.loads(task_path().read_text())
        self.c = {"root": str(self.root), "task": self.task, "episode_id": "offline_fixture",
                  "registry_valid": True, "frames": [], "transitions": [], "adb_trace": [],
                  "capabilities": {k: True for k in ("adb", "ui_dump", "screenshot", "runtime_probe", "preferences")},
                  "installed_apk": {"package": PACKAGE, "sha256": "a"*64, "expected_sha256": "a"*64},
                  "pipeline_error": None}
        self.ops, self.events = [], []
        self.frame("open")
        for item in self.task["expected_items"]:
            cases = [({"type":"type_text", "element_id":"search_input", "text":item["query"]},
                      {"type":"draft", "text":item["query"]}, "enter_search"),
                     ({"type":"tap_element", "element_id":"search_button"},
                      {"type":"search", "query":item["query"]}, "search"),
                     ({"type":"tap_element", "element_id":"add_"+item["sku"]},
                      {"type":"add", "sku":item["sku"]}, "add_to_cart")]
            for action, op, event in cases:
                self.step(action, op, event)
        self.step({"type":"tap_element", "element_id":"cart_button"}, {"type":"cart"}, "open_cart")

    def frame(self, event):
        index = len(self.c["frames"])
        state = replay_operations(self.ops, self.c["episode_id"])
        self.events.append({"sequence":index, "action":event, "accepted":True, "error":"", "state":copy.deepcopy(state)})
        state["events"] = copy.deepcopy(self.events)
        xml = '<hierarchy>' + ''.join('<node package="'+PACKAGE+'" resource-id="'+PACKAGE+':id/'+v+
                    '" enabled="true" clickable="true" class="android.widget.EditText" bounds="[0,0][100,100]"/>' for v in TARGETS) + '</hierarchy>'
        frame = {"index":index, "episode_id":self.c["episode_id"], "stable":True, "errors":[],
                 "state":state, "ui":nodes(xml), "artifacts":{}}
        raw = {"runtime.json":json.dumps(state), "runtime_before.json":json.dumps(state),
               "preferences.xml":'<map><string name="snapshot">'+escape(json.dumps(state))+'</string></map>',
               "journal.json":json.dumps(self.events), "ui.xml":xml}
        for name, value in raw.items():
            path = self.root / "frames" / f"{index:03d}" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
            frame["artifacts"][name] = {"path":str(path.relative_to(self.root)), "sha256":digest(path.read_bytes())}
        self.c["frames"].append(frame)

    def step(self, action, op, event):
        self.ops.append(op)
        self.frame(event)
        i = len(self.c["transitions"])
        self.c["adb_trace"].append({"returncode":0, "args":["shell", "input", "tap", "1", "1"]})
        self.c["transitions"].append({"raw_response":json.dumps(action), "action":action,
            "trace_start":i, "trace_end":i+1, "receipt":{"requested_action":action, "executed":True,
             "accepted":True, "failure_origin":"none"}})

    def test_full_cart_has_fourteen_passing_policies(self):
        result = evaluate(self.c)
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(len(result["policies"]), 14)
        self.assertEqual(sum(len(p["verifier_results"]) for p in result["policies"]), 70)
        self.assertTrue(cart_complete(self.c["frames"][-1]["state"], self.task))

    def test_registry_has_seventy_distinct_functions(self):
        self.assertEqual(len(load_registry()["policies"]), 14)
        self.assertEqual(len(VERIFIERS), 70)
        self.assertEqual(len({id(v[1]) for v in VERIFIERS.values()}), 70)

    def test_duplicate_quantity_fails(self):
        sku = self.task["expected_items"][0]["sku"]
        self.step({"type":"tap_element", "element_id":"increase_"+sku},
                  {"type":"adjust", "sku":sku, "delta":1}, "increase_quantity")
        self.assertEqual(evaluate(self.c)["status"], "FAIL")

    def test_missing_terminal_evidence_invalid(self):
        self.c["frames"][-1]["artifacts"] = {}
        result = evaluate(self.c)
        self.assertEqual(result["status"], "INVALID")
        self.assertFalse(result["training_eligible"])

    def test_rejected_action_fails_contract(self):
        self.c["transitions"][0]["receipt"]["accepted"] = False
        self.assertEqual(evaluate(self.c)["status"], "FAIL")

    def test_transport_failure_is_invalid(self):
        self.c["pipeline_error"] = "ADB unavailable"
        for t in self.c["transitions"]:
            t["receipt"]["failure_origin"] = "pipeline"
        self.assertEqual(evaluate(self.c)["status"], "INVALID")

    def test_tampered_runtime_is_not_a_vote(self):
        f = self.c["frames"][-1]
        (self.root / f["artifacts"]["runtime.json"]["path"]).write_text('{}')
        p = next(p for p in evaluate(self.c)["policies"] if p["policy_id"] == "T1")
        self.assertEqual(p["verifier_results"][1]["status"], "INVALID")

    def test_incomplete_cart_cannot_finish(self):
        self.assertFalse(cart_complete(self.c["frames"][0]["state"], self.task))

    def test_exact_scoring_for_all_243_vote_combinations(self):
        for votes in itertools.product((-1, 0, 1), repeat=5):
            rows = [{"verifier_id":f"T1.V{i}", "status":{v:k for k,v in REWARDS.items()}[v],
                     "reward":v, "reason_code":"FIXTURE", "evidence_refs":[]} for i,v in enumerate(votes, 1)]
            expected = 0 if all(v==0 for v in votes) else 1 if votes.count(1)>=2 else -1
            self.assertEqual(score_policy("T1", rows)["reward"], expected)

    def test_nonobject_actions_are_controlled_errors(self):
        for raw in ('[]', 'null', 'true', '"tap"'):
            self.assertIsNotNone(schema_error(decode(raw)))
        self.assertIsNotNone(permission_error({"type":"type_text", "element_id":"search_input", "text":"$(id)"}))
