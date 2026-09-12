"""Evidence-backed scoring for the separate peach SQLite app.

Five slots per policy retain the existing scoring rule. Unimplemented visual
readers explicitly abstain. SQLite/provider/journal are correlated, not three
independent sources; no actor statement is accepted as cart evidence.
"""
import json
from pathlib import Path
from amazon_cart_001.harness.actions import decode, schema_error
from amazon_cart_001.harness.peach import PACKAGE, PROFILE, CART_TARGETS, database_tables, permission_error, target_node
from amazon_cart_001.harness.evidence import digest
from amazon_cart_001.verification.contracts import Unassessable, require
from amazon_cart_001.verification.scoring import POLICY_IDS, REWARDS, score_policy, score_episode
from amazon_cart_001.verification.progress import weighted_stage_result

TASK_PATH = Path(__file__).resolve().parents[1]/"specs"/"peach_task.json"


def task_spec():
    return json.loads(TASK_PATH.read_text())


def replay(tables, episode):
    products = {p["id"]:p for p in tables["products"]}
    session = tables["eval_session"]
    require(len(session)==1 and session[0]["episode_id"]==episode, "EPISODE_MISMATCH")
    events = tables["eval_events"]
    require(bool(events), "JOURNAL_MISSING")
    cart, searches, additions = {}, [], []
    page, draft, query = "home", "", ""
    latest = None
    for index,event in enumerate(events):
        require(event["sequence"]==index, "JOURNAL_SEQUENCE_GAP")
        kind, payload = event["kind"], json.loads(event["payload"])
        if index==0:
            require(kind=="reset" and payload=={"episode_id":episode}, "RESET_MISSING")
            continue
        require(kind!="reset", "UNEXPECTED_RESET")
        if kind=="viewport":
            page,draft,query = (payload[k] for k in ("page","draft","query"))
        elif kind=="search":
            query = draft = payload["query"]
            require(isinstance(query,str) and bool(query.strip()), "UNREADABLE_SEARCH")
            matches = [p["sku"] for p in products.values() if all(
                word in (p["name"]+" "+p["category"]+" "+p["sku"]).lower()
                for word in query.lower().split())]
            latest = {"search_id":index, "query":query, "result_skus":matches}
            searches.append(latest)
        elif kind in {"add","decrease","remove"}:
            pid,qty = payload["product_id"],payload["quantity_after"]
            require(pid in products and type(qty) is int, "BAD_MUTATION_PRODUCT")
            previous = cart.get(pid,0)
            expected = previous+1 if kind=="add" else max(0,previous-1) if kind=="decrease" else 0
            require(qty==expected and 0<=qty<=99, "MUTATION_QUANTITY_MISMATCH")
            if kind=="add":
                sku = products[pid]["sku"]
                source = latest["search_id"] if (latest and page in {"results","detail"} and
                    query==latest["query"] and sku in latest["result_skus"]) else None
                additions.append({"sku":sku,"search_id":source,"quantity_after":qty})
            if qty: cart[pid]=qty
            else: cart.pop(pid,None)
        else:
            raise Unassessable("UNKNOWN_MUTATION_KIND")
    require((page,draft,query)==tuple(session[0][k] for k in ("page","draft","query")), "VIEWPORT_REPLAY_MISMATCH")
    actual = {r["product_id"]:r["qty"] for r in tables["cart"]}
    require(cart==actual and len(actual)==len(tables["cart"]), "CART_REPLAY_MISMATCH")
    return {"cart":cart,"searches":searches,"additions":additions,"page":page,"query":query,"draft":draft}


def snapshot(tables, episode):
    history = replay(tables,episode)
    products = {p["id"]:p for p in tables["products"]}
    rows=[]
    for row in tables["cart"]:
        require(row["product_id"] in products and type(row["qty"]) is int and row["qty"]>0, "BAD_CART_ROW")
        p=products[row["product_id"]]
        rows.append({"sku":p["sku"],"name":p["name"],"quantity":row["qty"],
            "unit_price_paise":p["price_paise"],"line_total_paise":p["price_paise"]*row["qty"]})
    return {"episode_id":episode,"cart":rows,"searches":history["searches"],"additions":history["additions"],
        "screen":"CART" if history["page"]=="cart" else "BROWSE", "page":history["page"],
        "draft":history["draft"],"query":history["query"],"currency":"INR","simulated":True,
        "cart_count":sum(r["quantity"] for r in rows),"distinct_cart_items":len(rows),
        "subtotal_paise":sum(r["line_total_paise"] for r in rows)}


def endpoint(policy, state, task):
    actual={r["sku"]:r for r in state["cart"]}
    wanted={r["sku"]:r for r in task["expected_items"]}
    exact=set(actual)==set(wanted)
    if policy=="T1":
        return exact and all(actual[s]["name"]==w["name"] for s,w in wanted.items())
    if policy=="T2":
        return exact and all(actual[s]["quantity"]==w["quantity"] for s,w in wanted.items())
    if policy=="T3":
        return exact and state["currency"]==task["currency"] and all(actual[s]["unit_price_paise"]==w["unit_price_paise"] for s,w in wanted.items())
    if policy=="T4":
        ids={s:{a["search_id"] for a in state["additions"] if a["sku"]==s and a["search_id"] is not None} for s in wanted}
        keys=list(wanted)
        return any(len({a,b,c})==3 for a in ids[keys[0]] for b in ids[keys[1]] for c in ids[keys[2]])
    if policy=="T5":
        return exact and state["cart_count"]==3 and state["distinct_cart_items"]==3 and state["subtotal_paise"]==task["expected_subtotal_paise"]
    if policy=="T6":
        return state["screen"]=="CART" and state["simulated"]
    raise ValueError(policy)


def cart_complete(state,task):
    return all(endpoint(p,state,task) for p in ("T1","T2","T3","T4","T5","T6"))


def progress(state, task):
    if not state:
        return {"completed_stages":0,"total_stages":6,"stages":[],"stage_result":weighted_stage_result([]),"final_result":weighted_stage_result([])["value"],"is_evaluation_reward":False}
    cart={r["sku"]:r for r in state["cart"]}
    stages=[]
    for item in task["expected_items"]:
        searched=any(item["sku"] in s["result_skus"] for s in state["searches"])
        present=cart.get(item["sku"],{}).get("quantity")==item["quantity"]
        for label,passed in (("searched",searched),("in_cart",present)):
            stages.append({"id":item["sku"]+"."+label,"complete":passed})
    return {"completed_stages":sum(s["complete"] for s in stages),"total_stages":6,
        "stages":stages,"stage_result":weighted_stage_result(stages),"final_result":weighted_stage_result(stages)["value"],"is_evaluation_reward":False}


def read_frame(context, frame, channel):
    root=Path(context["root"])
    names={"sqlite":"database.sqlite","provider":"runtime.json","journal":"runtime.json"}
    name=names[channel]
    require(frame.get("stable") and frame["episode_id"]==context["episode_id"],"UNSTABLE_FRAME")
    ref=frame["artifacts"][name]
    path=(root/ref["path"]).resolve()
    require(path.is_relative_to(root.resolve()),"EVIDENCE_PATH_ESCAPE")
    raw=path.read_bytes()
    require(digest(raw)==ref["sha256"],"EVIDENCE_HASH_MISMATCH")
    tables=database_tables(raw) if channel=="sqlite" else json.loads(raw)
    return snapshot(tables,context["episode_id"])


def acceptance(action,before,after):
    previous=before["tables"]; current=after["tables"]
    b=snapshot(previous,before["episode_id"]); a=snapshot(current,after["episode_id"])
    new=current["eval_events"][len(previous["eval_events"]):]
    events=[(e["kind"],json.loads(e["payload"])) for e in new]
    kind,target=action["type"],action.get("element_id","")
    if kind=="type_text": return a["draft"]==action["text"]
    if kind=="finish": return cart_complete(a,task_spec())
    if kind in {"wait","swipe","press_back"}: return True
    if target=="search_button":
        return a["page"]=="results" and any(k=="search" and p["query"]==b["draft"].strip() for k,p in events)
    if target in CART_TARGETS: return a["page"]=="cart"
    if target=="continue_shopping_button": return a["page"]=="home"
    if target.startswith("view_"): return a["page"]=="detail"
    prefix,_,sku=target.partition("_")
    event_kind={"add":"add","increase":"add","decrease":"decrease","remove":"remove"}.get(prefix)
    bysku={p["sku"]:p["id"] for p in current["products"]}
    return bool(event_kind and any(k==event_kind and p["product_id"]==bysku.get(sku) for k,p in events))


def generic(policy,channel,c):
    ts=c["transitions"]
    if policy=="V1":
        require(c.get("installed_apk",{}).get("package")==PACKAGE and
                c["installed_apk"]["sha256"]==c["installed_apk"]["expected_sha256"] and
                c["task"].get("variant")==PROFILE,"READINESS_NOT_ESTABLISHED")
        require(bool(c["frames"]), "INITIAL_FRAME_MISSING")
        read_frame(c,c["frames"][0],"sqlite" if channel==1 else "provider")
        return True
    if policy=="V2":
        for f in c["frames"]: read_frame(c,f,"sqlite" if channel==1 else "provider")
        require(len(c["frames"])==len(ts)+1,"FRAME_COUNT_MISMATCH")
        return True
    if policy=="G1":
        return all(schema_error(decode(t["raw_response"]) if channel==1 else t["action"]) is None for t in ts)
    if policy=="G2":
        return all(permission_error(decode(t["raw_response"]) if channel==1 else t["action"]) is None for t in ts)
    if policy=="G3":
        for t in ts:
            if schema_error(t["action"]): return False
            ui=c["frames"][t["before_frame"]]["ui"] if channel==1 else t["dispatch_ui"]
            try: target_node(t["action"],ui)
            except ValueError: return False
        return True
    if policy=="G4":
        for t in ts:
            r=t["receipt"]
            require(r["failure_origin"]!="pipeline","TRANSPORT_UNASSESSABLE")
            if not r["executed"]: return False
            if channel==1:
                entries=c["adb_trace"][t["trace_start"]:t["trace_end"]]
                if t["action"]["type"] not in {"wait","finish"}:
                    require(any(e["args"][:2]==["shell","input"] for e in entries),"NO_EXECUTION_COMMAND")
                require(all(e.get("returncode")==0 and not e.get("error") for e in entries),"ADB_EXECUTION_UNASSESSABLE")
            elif not r["execution_receipt"]: raise Unassessable("MISSING_DISPATCH_RECEIPT")
        return True
    if policy=="S1":
        wanted={r["sku"] for r in c["task"]["expected_items"]}
        for t in ts:
            action=t["action"]
            if schema_error(action): return False
            target=action.get("element_id","")
            if target.startswith(("add_","increase_")) and target.split("_",1)[1] not in wanted: return False
            if not t["receipt"]["accepted"]: return False
            if channel==2 and not acceptance(action,c["frames"][t["before_frame"]],c["frames"][t["after_frame"]]): return False
        return True
    if policy=="T7":
        for t in ts:
            if schema_error(decode(t["raw_response"])) or permission_error(t["action"]): return False
            if not t["receipt"]["executed"] or not t["receipt"]["accepted"]: return False
            if channel==2 and not acceptance(t["action"],c["frames"][t["before_frame"]],c["frames"][t["after_frame"]]): return False
        return len(ts)<=c["task"]["max_steps"]
    raise ValueError(policy)


def evaluate(c):
    policies=[]
    for pid in POLICY_IDS:
        results=[]
        for number in range(1,6):
            refs=[]
            channel=("sqlite","provider","journal","accessibility","screenshot_ocr")[number-1] if pid in {"T1","T2","T3","T4","T5","T6"} else ("primary_audit","cross_audit","reserved_independent_audit","reserved_visual_audit","reserved_external_audit")[number-1]
            try:
                require(not c.get("pipeline_error"),"PIPELINE_ERROR")
                if pid in {"T1","T2","T3","T4","T5","T6"}:
                    require(number<=3,"VISUAL_READER_NOT_IMPLEMENTED_FOR_PEACH")
                    frame=c["frames"][-1]
                    state=read_frame(c,frame,channel)
                    passed=endpoint(pid,state,c["task"])
                    refs=[frame["artifacts"]["database.sqlite" if number==1 else "runtime.json"]["path"]]
                else:
                    require(number<=2,"ADDITIONAL_FULL_CLAIM_READER_UNAVAILABLE")
                    passed=generic(pid,number,c)
                    refs=["context.json","trajectory.jsonl","adb_actions.jsonl"]
                status="PASS" if passed else "FAIL"
                reason="CLAIM_CONFIRMED" if passed else "ASSESSABLE_CLAIM_NOT_SATISFIED"
            except (Unassessable,KeyError,TypeError,ValueError,OSError,IndexError) as error:
                status,reason="INVALID",str(error) or type(error).__name__
            results.append({"verifier_id":f"{pid}.V{number}","implementation":f"peach.{pid}.{channel}",
                "status":status,"reward":REWARDS[status],"reason_code":reason,"evidence_refs":refs,
                "failure_origin":"pipeline" if status=="INVALID" else "agent" if status=="FAIL" else "none"})
        policies.append(score_policy(pid,results))
    result=score_episode(policies)
    result["evidence_profile"]=PROFILE
    result["correlation_notice"]="SQLite, provider and mutation journal share the same app database. Reserved/visual readers abstain, never fabricate PASS."
    result["implemented_verifier_slots"]=34
    return result

