from amazon_cart_001.specs import task_path, fingerprints
from amazon_cart_001 import VERSION
import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from amazon_cart_001.harness.actions import decode, schema_error, permission_error
from amazon_cart_001.harness.device import Device
from amazon_cart_001.harness.evidence import save, digest
from amazon_cart_001.verification.registry import load_registry, evaluate
from amazon_cart_001.verification.progress import progress
from amazon_cart_001.verification.generic.interaction import target_ok
from amazon_cart_001.verification.task_checks import endpoint_test, cart_complete


class Episode:
    def __init__(self, serial, apk, output, adb="adb"):
        self.device = Device(serial, adb)
        self.task = json.loads(task_path().read_text())
        load_registry()
        self.episode = "cart_eval_" + uuid4().hex
        self.root = Path(output) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
        self.root.mkdir(parents=True, exist_ok=False)
        self.apk, self.frames, self.transitions, self.history = apk, [], [], []
        self.error, self.done, self.verdict = None, False, None
        self.context = {"root":str(self.root.resolve()),"task":self.task,"episode_id":self.episode,
            "registry_valid":True,"frames":self.frames,"transitions":self.transitions,"adb_trace":self.device.trace,
            "capabilities":{},"installed_apk":{},"implementation_hashes":fingerprints()}
        save(self.root / "provenance.json", {"execution_location":"local-server-kvm","runtime_version":VERSION,
             "implementation_hashes":fingerprints(),"task_sha256":digest(task_path().read_bytes()),
             "episode_id":self.episode,"registry":load_registry()})

    def reset(self):
        self.context["installed_apk"] = self.device.installed(self.apk)
        save(self.root / "installed_apk.json", self.context["installed_apk"])
        self.device.start(self.episode)
        frame = self.device.capture(self.root, 0, self.episode)
        self.frames.append(frame)
        if frame["errors"]:
            self.error = "; ".join(frame["errors"])
        else:
            self.context["capabilities"] = {k:True for k in ("adb","ui_dump","screenshot","runtime_probe","preferences")}
        self.checkpoint()
        return frame

    def step(self, raw):
        if self.done or len(self.transitions) >= self.task["max_steps"]:
            raise RuntimeError("Episode already stopped")
        before = self.frames[-1]
        action = decode(raw)
        receipt = {"requested_action":action,"schema_valid":schema_error(action) is None,
                   "permitted":False,"executed":False,"accepted":None,"failure_origin":"none","error":None}
        begin = len(self.device.trace)
        self.device.phase = "action"
        err = schema_error(action) or permission_error(action)
        receipt["permitted"] = permission_error(action) is None
        target = None
        if not err and not target_ok(action, before):
            err = "Target is not visible, enabled and interactable; scroll if necessary"
        if not err and action["type"] == "swipe":
            image = before["artifacts"]["screen.png"]
            data = (self.root / image["path"]).read_bytes()
            w, h = int.from_bytes(data[16:20],"big"), int.from_bytes(data[20:24],"big")
            if not all(0 <= action[k] < limit for k,limit in (("x1",w),("x2",w),("y1",h),("y2",h))):
                err = "Swipe coordinates outside the screenshot"
        if not err and action["type"] == "finish" and not cart_complete(before["state"], self.task):
            err = "Cart task incomplete; finish rejected. Continue within the remaining budget."
        if err:
            receipt.update(error=err, failure_origin="agent", accepted=False)
        else:
            try:
                if action["type"] in {"tap_element","type_text"}:
                    from amazon_cart_001.harness.evidence import nodes
                    fresh_ui = nodes(self.device.ui())
                    fresh = {**before,"ui":fresh_ui}
                    if not target_ok(action, fresh):
                        raise RuntimeError("UI changed between observation and execution")
                    target = next(n for n in fresh_ui if n["id"] == action["element_id"])
                self.device.execute(action, target)
                receipt["executed"] = True
            except Exception as exc:
                receipt.update(error=type(exc).__name__+": "+str(exc),failure_origin="pipeline")
                self.error = receipt["error"]
        end = len(self.device.trace)
        after = self.device.capture(self.root, len(self.frames), self.episode)
        self.frames.append(after)
        if after["errors"]:
            self.error = "; ".join(after["errors"])
            receipt.update(error=self.error, failure_origin="pipeline")
        elif receipt["executed"]:
            from amazon_cart_001.harness.acceptance import assess_acceptance
            receipt.update(assess_acceptance(action,before,after))
            if receipt["failure_origin"] == "pipeline":
                self.error = receipt["error"]
        transition = {"step":len(self.transitions)+1,"raw_response":raw,"action":action,"receipt":receipt,
                      "before_frame":before["index"],"after_frame":after["index"],"trace_start":begin,"trace_end":end}
        self.transitions.append(transition)
        self.done = bool(self.error or len(self.transitions) >= self.task["max_steps"] or
                         (action == {"type":"finish"} and receipt["executed"] and receipt["accepted"]))
        self.checkpoint()
        return after

    def checkpoint(self):
        self.context["pipeline_error"] = self.error
        save(self.root / "context.json", self.context)
        (self.root / "trajectory.jsonl").write_text("".join(json.dumps(t)+"\n" for t in self.transitions))
        (self.root / "adb_actions.jsonl").write_text("".join(json.dumps(t)+"\n" for t in self.device.trace))
        verdict = evaluate(self.context)
        point = progress(self.frames[-1].get("state",{}), self.task)
        point.update(step=len(self.transitions),policy_results=verdict["policies"],
                     episode_reward=None,episode_status="PENDING",screenshot=self.frames[-1]["artifacts"].get("screen.png"))
        self.history.append(point)
        save(self.root / "checkpoints" / f"{len(self.transitions):03d}.json",point)
        save(self.root / "progress_history.json",self.history)
        save(self.root / "frames" / f'{self.frames[-1]["index"]:03d}' / "frame.json",self.frames[-1])
        return point

    def message(self):
        frame = self.frames[-1]
        public = {"goal":self.task["goal"],"step":len(self.transitions),"max_steps":self.task["max_steps"],
                  "ui":frame.get("ui",[]),"last_error":self.transitions[-1]["receipt"]["error"] if self.transitions else None}
        content = [{"type":"text","text":json.dumps(public,ensure_ascii=False)}]
        ref = frame.get("artifacts",{}).get("screen.png")
        if ref:
            content.append({"type":"image_url","image_url":{"url":"data:image/png;base64,"+
                base64.b64encode((self.root/ref["path"]).read_bytes()).decode()}})
        return {"role":"user","content":content}

    def finalize(self):
        self.context["pipeline_error"] = self.error
        self.verdict = evaluate(self.context)
        self.verdict["progress"] = progress(self.frames[-1].get("state",{}),self.task) if self.frames else {}
        if self.history:
            self.history[-1].update(episode_reward=self.verdict["reward"],episode_status=self.verdict["status"],
                                    policy_results=self.verdict["policies"])
            save(self.root / "progress_history.json", self.history)
            save(self.root / "checkpoints" / f"{len(self.transitions):03d}.json", self.history[-1])
        self.done = True
        save(self.root / "context.json",self.context)
        save(self.root / "verdict.json",self.verdict)
        save(self.root / "verifier_results.json",self.verdict["policies"])
        if self.frames:
            save(self.root/"initial_state.json",self.frames[0].get("state"))
            save(self.root/"final_state.json",self.frames[-1].get("state"))
        return self.verdict
