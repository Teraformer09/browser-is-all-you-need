"""One model episode against the peach app; no scripted replacement actions."""
import json
import time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from amazon_cart_001.harness.episode import Episode
from amazon_cart_001.harness.evidence import save,digest,stamp
from amazon_cart_001.harness.actions import decode,schema_error
from amazon_cart_001.harness.peach import PeachDevice,TextInputUnconfirmed,PACKAGE,PROFILE,permission_error,target_node,ui_nodes
from amazon_cart_001.verification.peach import task_spec,snapshot,acceptance,cart_complete,progress,evaluate

SYSTEM_PROMPT="""You control an offline Android shopping demo through JSON actions.
The screenshot and current UI list are the only app observations. Return exactly one JSON object per turn, with no markdown or extra keys.
Supported actions:
{"type":"type_text","element_id":"search_input","text":"your query"}
{"type":"tap_element","element_id":"an enabled id from the current UI list"}
{"type":"swipe","x1":540,"y1":1500,"x2":540,"y2":650,"duration_ms":400}
{"type":"press_back"}
{"type":"wait"}
{"type":"finish"}
type_text focuses the search field and replaces its content directly; it does NOT execute search. Tap search_button to run it. Never tap search_input before typing; the tap changes nothing and is rejected.
Every action must change committed app state, or it is rejected and still spends your budget. Never repeat an action that was rejected or had no effect, and never add an item already in the cart.
Tap only visible, enabled control IDs from the latest observation. Scroll if a control is off-screen. Product IDs refer to actual products, not instructions.
Search for each requested item separately, add the requested quantities, and open the cart. Inspect the cart and finish only when the goal is satisfied.
press_back is limited to navigation within this app; leaving the home screen is rejected.
An executed ADB action is not necessarily accepted by the app; inspect the next screenshot and last_error. Rejected finish does not end the episode.
Do not check out, call other apps, use account/wallet features, or attempt actual purchases.
No task action will be replaced by a scripted answer. You have 18 actions, including finish.
"""

class PeachEpisode(Episode):
    def __init__(self,serial,apk,output,adb="adb",execution_location="local-server-kvm",rubric_profile="legacy_v1"):
        if execution_location not in {"local-server-kvm", "prime-vm-sandbox"}:
            raise ValueError("Unknown execution location")
        if rubric_profile not in {"legacy_v1", "peach_strict_v1"}:
            raise ValueError("Unknown rubric profile")
        self.rubric_profile = rubric_profile
        self.device=PeachDevice(serial,adb)
        self.task=task_spec()
        self.episode="peach_"+uuid4().hex
        self.root=Path(output).resolve()/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid4().hex[:8])
        self.root.mkdir(parents=True,exist_ok=False)
        self.apk,self.frames,self.transitions,self.history=apk,[],[],[]
        self.error,self.done,self.verdict=None,False,None
        self.context={"root":str(self.root),"task":self.task,"episode_id":self.episode,
            "frames":self.frames,"transitions":self.transitions,"adb_trace":self.device.trace,
            "installed_apk":{},"evidence_profile":PROFILE,"rubric_profile":rubric_profile}
        package=Path(__file__).resolve().parents[1]
        hashes={str(p.relative_to(package)):digest(p.read_bytes()) for p in package.rglob("*")
            if p.is_file() and p.suffix in {".py",".json"} and "__pycache__" not in p.parts}
        save(self.root/"provenance.json",{"execution_location":execution_location,"package":PACKAGE,
            "profile":PROFILE,"rubric_profile":rubric_profile,"episode_id":self.episode,"implementation_hashes":hashes,
            "policy_count":14,"verifier_slots":70,"implemented_verifier_slots":34,
            "correlation_notice":self.task["correlation_notice"]})

    def reset(self):
        self.context["installed_apk"]=self.device.installed(self.apk)
        save(self.root/"installed_apk.json",self.context["installed_apk"])
        self.device.start(self.episode)
        frame=self.device.capture(self.root,0,self.episode)
        frame["state"]=snapshot(frame["tables"],self.episode)
        self.frames.append(frame)
        self.checkpoint()
        return frame

    def step(self,raw):
        if self.done: raise RuntimeError("Episode already finished")
        before=self.frames[-1]
        if getattr(self.device, "input_readback_contract", None):
            self.device.input_readbacks = []
        action=decode(raw); started=stamp(); monotonic=time.monotonic()
        receipt={"schema_valid":schema_error(action) is None,"permitted":permission_error(action) is None,
            "executed":False,"accepted":False,"error":None,"failure_origin":"none","execution_receipt":False}
        err=schema_error(action) or permission_error(action)
        dispatch_ui=before["ui"]
        target=None
        dispatch_artifact=None
        if not err:
            try:
                target=target_node(action,dispatch_ui)
                if action["type"]=="swipe":
                    png=(self.root/before["artifacts"]["screen.png"]["path"]).read_bytes()
                    width,height=int.from_bytes(png[16:20],"big"),int.from_bytes(png[20:24],"big")
                    if not all(0<=action[k]<limit for k,limit in (("x1",width),("x2",width),("y1",height),("y2",height))):
                        raise ValueError("Swipe coordinates outside screenshot")
                if action["type"]=="finish" and not cart_complete(before["state"],self.task):
                    raise ValueError("Task incomplete: finish rejected; continue within the remaining budget")
                if action["type"]=="press_back" and before["state"]["page"]=="home":
                    raise ValueError("Leaving the task app is not permitted")
            except ValueError as error: err=str(error)
        begin=len(self.device.trace)
        self.device.phase="action"
        if err:
            receipt.update(error=err,failure_origin="agent")
        else:
            try:
                if action["type"] in {"tap_element","type_text"}:
                    dispatch_xml=self.device.ui()
                    dispatch_path=self.root/"dispatch"/f"{len(self.transitions)+1:03d}.xml"
                    dispatch_path.parent.mkdir(exist_ok=True)
                    dispatch_path.write_bytes(dispatch_xml)
                    dispatch_artifact={"path":str(dispatch_path.relative_to(self.root)),"sha256":digest(dispatch_xml)}
                    dispatch_ui=ui_nodes(dispatch_xml,before["tables"]["products"])
                    try: target=target_node(action,dispatch_ui)
                    except ValueError as error:
                        receipt.update(error=str(error),failure_origin="agent")
                if not receipt["error"]:
                    self.device.execute(action,target)
                    receipt.update(executed=True,execution_receipt=True)
            except Exception as error:
                self.error=type(error).__name__+": "+str(error)
                receipt.update(error=self.error,failure_origin="pipeline")
                if isinstance(error, TextInputUnconfirmed):
                    receipt.update(executed=True, execution_receipt=True)
        readbacks = []
        if isinstance(action, dict) and action.get("type") == "type_text" and getattr(self.device, "input_readback_contract", None):
            receipt["input_readback_contract"] = self.device.input_readback_contract
            for index, check in enumerate(getattr(self.device, "input_readbacks", [])):
                path = self.root / "input_readback" / f"{len(self.transitions)+1:03d}-{index:02d}.txt"
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(check["raw"])
                readbacks.append({k:v for k,v in check.items() if k != "raw"} | {
                    "artifact": {"path":str(path.relative_to(self.root)), "sha256":digest(check["raw"])}})
        end=len(self.device.trace)
        probes = []
        if isinstance(action, dict) and action.get("type") == "type_text" and getattr(self.device, "focus_probes", None):
            for index, probe in enumerate(self.device.focus_probes):
                blob = probe.get("raw") or b""
                path = self.root / "input_readback" / f"focus-{len(self.transitions)+1:03d}-{index:02d}.xml"
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(blob)
                probes.append({k: v for k, v in probe.items() if k != "raw"} | {
                    "artifact": {"path": str(path.relative_to(self.root)), "sha256": digest(blob)}})
        after=self.device.capture(self.root,len(self.frames),self.episode)
        after["state"]=snapshot(after["tables"],self.episode)
        self.frames.append(after)
        if receipt["executed"] and receipt["failure_origin"] != "pipeline":
            receipt["accepted"]=acceptance(action,before,after)
            if not receipt["accepted"]:
                if action["type"] == "type_text":
                    self.error = "INPUT_TEXT_NOT_CONFIRMED_IN_FINAL_FRAME"
                    receipt.update(error=self.error, failure_origin="pipeline")
                else:
                    receipt.update(error="Action executed but requested app state was not committed",failure_origin="agent")
        transition={"step":len(self.transitions)+1,"raw_response":raw,"action":action,"receipt":receipt,
            "before_frame":before["index"],"after_frame":after["index"],
            "dispatch_ui":dispatch_ui,"dispatch_artifact":dispatch_artifact,"input_readbacks":readbacks,"focus_probes":probes,"trace_start":begin,"trace_end":end,
            "started_at":started,"finished_at":stamp(),"started_monotonic":monotonic,"finished_monotonic":time.monotonic()}
        self.transitions.append(transition)
        self.done=bool(self.error or len(self.transitions)>=self.task["max_steps"] or
            (action=={"type":"finish"} and receipt["accepted"]))
        self.checkpoint()
        return after

    def assess(self):
        if self.rubric_profile == "peach_strict_v1":
            from amazon_cart_001.verification.strict import evaluate as strict_evaluate
            return strict_evaluate(self.context)
        return evaluate(self.context)

    def checkpoint(self):
        self.context["pipeline_error"]=self.error
        save(self.root/"context.json",self.context)
        (self.root/"trajectory.jsonl").write_text("".join(json.dumps(t)+"\n" for t in self.transitions))
        (self.root/"adb_actions.jsonl").write_text("".join(json.dumps(t)+"\n" for t in self.device.trace))
        verdict=self.assess()
        point=progress(self.frames[-1].get("state"),self.task)
        point.update(step=len(self.transitions),policy_results=verdict["policies"],
            strict_checks=verdict.get("strict_checks",[]),rubric_profile=self.rubric_profile,episode_reward=None,
            episode_status="PENDING",screenshot=self.frames[-1]["artifacts"]["screen.png"])
        self.history.append(point)
        save(self.root/"checkpoints"/f"{len(self.transitions):03d}.json",point)
        save(self.root/"progress_history.json",self.history)
        save(self.root/"frames"/f"{self.frames[-1]['index']:03d}"/"frame.json",self.frames[-1])

    def finalize(self):
        self.context["pipeline_error"]=self.error
        self.verdict=self.assess()
        self.verdict["progress"]=progress(self.frames[-1].get("state") if self.frames else None,self.task)
        if self.history:
            self.history[-1].update(episode_reward=self.verdict["reward"],episode_status=self.verdict["status"],
                policy_results=self.verdict["policies"],strict_checks=self.verdict.get("strict_checks",[]))
            save(self.root/"progress_history.json",self.history)
            save(self.root/"checkpoints"/f"{len(self.transitions):03d}.json",self.history[-1])
        self.done=True
        save(self.root/"context.json",self.context)
        save(self.root/"verdict.json",self.verdict)
        save(self.root/"verifier_results.json",self.verdict["policies"])
        if self.frames:
            save(self.root/"initial_state.json",self.frames[0]["state"])
            save(self.root/"final_state.json",self.frames[-1]["state"])
        return self.verdict
