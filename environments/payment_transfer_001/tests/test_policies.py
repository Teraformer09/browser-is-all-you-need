from payment_transfer_001.verification.semantic import semantic_error
import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from xml.sax.saxutils import escape
from payment_transfer_001.harness.actions import decode, schema_error, permission_error
from payment_transfer_001.harness.evidence import digest
from payment_transfer_001.verification.registry import load_registry, evaluate
from payment_transfer_001.verification.registry import VERIFIERS
from payment_transfer_001.verification.progress import progress
from payment_transfer_001.specs import task_path
from payment_transfer_001.verification.scoring import POLICY_IDS, REWARDS, score_policy, score_episode

class ScoringTests(unittest.TestCase):
    def test_exhaustive_five_votes(self):
        for votes in itertools.product((-1,0,1),repeat=5):
            results = [{"verifier_id":f"T1.V{i}","status":{v:k for k,v in REWARDS.items()}[v],
                        "reward":v,"reason_code":"TEST","evidence_refs":[]} for i,v in enumerate(votes,1)]
            expected = 0 if all(v==0 for v in votes) else 1 if votes.count(1)>=2 else -1
            self.assertEqual(score_policy("T1",results)["reward"],expected)
    def test_registry_unique(self):
        r=load_registry()
        self.assertEqual(len(r["policies"]),14)
        self.assertEqual(len(VERIFIERS),70)
        self.assertEqual(len({id(v[1]) for v in VERIFIERS.values()}),70)
    def test_bad_id_invalid(self):
        self.assertEqual(score_policy("T1",[])["status"],"INVALID")
    def test_episode_precedence(self):
        for status in ("PASS","INVALID","FAIL"):
            rows=[{"policy_id":p,"status":"PASS","reward":1} for p in POLICY_IDS]
            rows[-1].update(status=status,reward=REWARDS[status])
            self.assertEqual(score_episode(rows)["status"],status)

class ActionTests(unittest.TestCase):
    def test_non_objects_and_extra_fields(self):
        for raw in ("[]","null","true","0",'"tap"','{"type":"wait","extra":1}'):
            self.assertIsNotNone(schema_error(decode(raw)))
    def test_exact_schema(self):
        self.assertIsNone(schema_error({"type":"type_text","element_id":"note_input","text":"Lunch"}))
    def test_unknown_target(self):
        self.assertIsNotNone(permission_error({"type":"tap_element","element_id":"bank_password"}))
    def test_shell_text_rejected(self):
        for text in ("$(id)","hi;ls","hello\nworld","a%sb"):
            self.assertIsNotNone(permission_error({"type":"type_text","element_id":"note_input","text":text}))
    def test_wrong_semantics(self):
        task=json.loads(task_path().read_text())
        self.assertIsNotNone(semantic_error({"type":"tap_element","element_id":"recipient_blair"},task["expected"]))

class PolicyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.task=json.loads(task_path().read_text())
        initial={"schema_version":1,"episode_id":"test_episode","simulated":True,"status":"DRAFT",
                 "revision":0,"reviewed_revision":-1,"recipient_id":"","account_id":"",
                 "amount_input":"","amount_paise":0,"currency":"INR","note":"","transactions":[]}
        self.c={"root":str(self.root),"task":self.task,"episode_id":"test_episode","registry_valid":True,
                "frames":[],"transitions":[],"adb_trace":[],"capabilities":{k:True for k in ("adb","ui_dump","screenshot","runtime_probe","preferences")},
                "installed_apk":{"package":self.task["package"],"sha256":"a"*64,"expected_sha256":"a"*64},
                "pipeline_error":None}
        self.events=[]
        self.add_frame(initial,"open")
        cases=[
          ({"type":"tap_element","element_id":"recipient_alex"},"select_recipient",{"recipient_id":"alex","revision":1}),
          ({"type":"type_text","element_id":"amount_input","text":"500"},"enter_amount",{"amount_input":"500","amount_paise":50000,"revision":2}),
          ({"type":"tap_element","element_id":"account_1234"},"select_account",{"account_id":"account_1234","revision":3}),
          ({"type":"type_text","element_id":"note_input","text":"Lunch"},"enter_note",{"note":"Lunch","revision":4}),
          ({"type":"tap_element","element_id":"review_button"},"review",{"reviewed_revision":4,"status":"REVIEW"}),
          ({"type":"tap_element","element_id":"confirm_transfer_button"},"confirm",{"status":"COMPLETED"})]
        for action,kind,changes in cases:
            s=copy.deepcopy(self.c["frames"][-1]["state"])
            for key in ("events","last_action","last_action_accepted","last_error"): s.pop(key,None)
            s.update(changes)
            if kind=="confirm":
                s["transactions"]=[{**self.task["expected"],"transaction_id":"12345678-1234-1234-1234-123456789012",
                    "episode_id":"test_episode","status":"COMPLETED","simulated":True,"reviewed_revision":4}]
            self.add_frame(s,kind)
            i=len(self.c["transitions"])
            self.c["adb_trace"].append({"returncode":0,"args":["shell","input","tap","1","1"]})
            self.c["transitions"].append({"raw_response":json.dumps(action),"action":action,
                "trace_start":i,"trace_end":i+1,"receipt":{"requested_action":action,"executed":True,
                "accepted":True,"failure_origin":"none"}})
    def tearDown(self):
        self.temp.cleanup()
    def add_frame(self,s,kind):
        index=len(self.c["frames"])
        self.events.append({"sequence":index,"action":kind,"accepted":True,"error":"","state":copy.deepcopy(s)})
        s.update(events=copy.deepcopy(self.events),last_action=kind,last_action_accepted=True,last_error="")
        frame={"index":index,"episode_id":"test_episode","stable":True,"errors":[],"state":s,"artifacts":{}}
        controls=("recipient_alex","recipient_blair","account_1234","account_5678","amount_input","note_input","review_button","confirm_transfer_button")
        xml='<hierarchy>'+''.join('<node package="'+self.task["package"]+'" resource-id="'+self.task["package"]+':id/'+v+'" text="" enabled="true" clickable="true" class="android.widget.EditText" bounds="[0,0][100,100]"/>' for v in controls)+'</hierarchy>'
        from payment_transfer_001.harness.evidence import nodes
        frame["ui"]=nodes(xml)
        data={"runtime.json":json.dumps(s),"runtime_before.json":json.dumps(s),
              "preferences.xml":'<map><string name="snapshot">'+escape(json.dumps(s))+'</string></map>',
              "journal.json":json.dumps(self.events),"ui.xml":xml,"screen.png":"TEST_ONLY_NOT_AN_IMAGE"}
        for name,value in data.items():
            path=self.root/"frames"/f"{index:03d}"/name
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
            frame["artifacts"][name]={"path":str(path.relative_to(self.root)),"sha256":digest(path.read_bytes())}
        self.c["frames"].append(frame)
    def test_completed_all_policies(self):
        result=evaluate(self.c)
        self.assertEqual(result["status"],"PASS",[(p["policy_id"],p["status"]) for p in result["policies"]])
        self.assertEqual(sum(len(p["verifier_results"]) for p in result["policies"]),70)
        self.assertEqual(progress(self.c["frames"][-1]["state"],self.task)["completed_stages"],6)
    def test_missing_terminal_channels_invalid(self):
        self.c["frames"][-1]["artifacts"]={}
        result=evaluate(self.c)
        self.assertEqual(next(p for p in result["policies"] if p["policy_id"]=="T1")["status"],"INVALID")
    def test_wrong_recipient_is_not_generic_success(self):
        self.c["task"]["expected"]["recipient_id"]="blair"
        result=evaluate(self.c)
        self.assertEqual(result["status"],"FAIL")
        self.assertEqual(next(p for p in result["policies"] if p["policy_id"]=="T1")["status"],"FAIL")
    def test_rejected_action_fails_contract(self):
        self.c["transitions"][0]["receipt"]["accepted"]=False
        result=evaluate(self.c)
        self.assertEqual(next(p for p in result["policies"] if p["policy_id"]=="T7")["status"],"FAIL")
    def test_transport_failure_invalid(self):
        self.c["pipeline_error"]="ADB disconnected"
        for t in self.c["transitions"]:t["receipt"]["failure_origin"]="pipeline"
        result=evaluate(self.c)
        self.assertEqual(result["status"],"INVALID")
        self.assertFalse(result["training_eligible"])
    def test_hash_tampering_invalidates_channel(self):
        f=self.c["frames"][-1]
        (self.root/f["artifacts"]["runtime.json"]["path"]).write_text("{}")
        votes=evaluate(self.c)["policies"]
        self.assertEqual(next(p for p in votes if p["policy_id"]=="T1")["verifier_results"][1]["status"],"INVALID")
    def test_model_action_mismatch_invalid(self):
        self.c["transitions"][0]["raw_response"]='{"type":"wait"}'
        result=evaluate(self.c)
        self.assertEqual(next(p for p in result["policies"] if p["policy_id"]=="G1")["status"],"INVALID")

if __name__=="__main__":
    unittest.main()
