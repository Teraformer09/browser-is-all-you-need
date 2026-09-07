from payment_transfer_001.verification.task_checks import endpoint_test
import copy
import json
import re
import xml.etree.ElementTree as ET


def progress(snapshot, task):
    expected = task["expected"]
    stages = {}
    for pid in ("T1","T2","T3","T4","T5","T6"):
        try:
            passed = endpoint_test(pid, snapshot, expected)
            stages[pid] = {"completed":bool(passed),"status":"PASS" if passed else "PENDING"}
        except (KeyError,TypeError):
            stages[pid] = {"completed":False,"status":"INVALID"}
    return {"completed_stages":sum(s["completed"] for s in stages.values()),"total_stages":6,
            "stages":stages,"diagnostic_only":True}
