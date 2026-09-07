"""Exact three-product cart and search-provenance checker; progress is not reward."""
from itertools import product

def result(status,reason,checks=None,stages=None):
    stages=stages or {}
    return {"status":status,"reward":{"PASS":1,"FAIL":-1,"INVALID":0}[status],
            "reason_code":reason,"checks":checks or {},"stages":stages,
            "completed_stages":sum(v["completed"] for v in stages.values()),"total_stages":6,
            "verifier_version":"shopping-cart-v1","policy_layer":"deterministic-cart-and-search",
            "training_eligible":False}

def verify(state,task,episode_id):
    try:
        items=task["expected_items"]
        if type(task["schema_version"]) is not int or task["schema_version"]!=1 or len(items)!=3 or len({i["sku"] for i in items})!=3:
            raise ValueError("Expected three distinct task products")
        for item in items:
            if not isinstance(item["sku"],str) or not item["sku"] or not isinstance(item["query"],str) or not item["query"].strip():
                raise ValueError("Missing task product/query")
            if type(item["quantity"]) is not int or item["quantity"]!=1 or type(item["unit_price_paise"]) is not int or item["unit_price_paise"]<=0:
                raise ValueError("Invalid expected quantity or price")
        if task["currency"]!="INR" or type(task["expected_subtotal_paise"]) is not int or task["expected_subtotal_paise"]!=sum(i["unit_price_paise"] for i in items):
            raise ValueError("Task total does not match its products")
    except (KeyError,TypeError,ValueError):
        return result("INVALID","TASK_SPECIFICATION_INVALID")
    try:
        if not isinstance(state,dict) or type(state["schema_version"]) is not int or state["schema_version"]!=1:
            raise ValueError("State schema unavailable")
        if state["episode_id"]!=episode_id or state["simulated"] is not True:
            raise ValueError("Wrong episode or non-simulated state")
        if state["screen"] not in {"BROWSE","CART"} or not isinstance(state["currency"],str):
            raise ValueError("State fields unreadable")
        for field in ("distinct_items","total_quantity","subtotal_paise","revision"):
            if type(state[field]) is not int or state[field]<0:raise ValueError("Invalid counter")
        searches,adds,cart=state["searches"],state["additions"],state["cart_items"]
        if not all(isinstance(v,list) for v in (searches,adds,cart)):raise ValueError("Missing records")
        by_search={}
        for i,s in enumerate(searches,1):
            if type(s["search_id"]) is not int or s["search_id"]!=i or not isinstance(s["query"],str) or len(s["query"].strip())<2:
                raise ValueError("Unattributed search")
            if not isinstance(s["result_skus"],list) or not all(isinstance(k,str) for k in s["result_skus"]):
                raise ValueError("Unreadable search results")
            by_search[i]=s
        for a in adds:
            if not isinstance(a["sku"],str) or type(a["search_id"]) is not int or a["search_id"] not in by_search:
                raise ValueError("Unattributed add")
            source=by_search[a["search_id"]]
            if a["query"]!=source["query"] or a["sku"] not in source["result_skus"]:
                raise ValueError("Add not backed by its search")
            if type(a["quantity_after"]) is not int or not 1<=a["quantity_after"]<=9:
                raise ValueError("Invalid add receipt")
        for row in cart:
            if not isinstance(row["sku"],str) or not isinstance(row["name"],str):raise ValueError("Unreadable product")
            if any(type(row[k]) is not int for k in ("quantity","unit_price_paise","line_total_paise")):
                raise ValueError("Unreadable quantity or money")
    except (KeyError,TypeError,ValueError):
        return result("INVALID","EVIDENCE_SCHEMA_OR_PROVENANCE_INVALID")
    rows={r["sku"]:r for r in cart}
    expected={item["sku"]:item for item in items}
    stages={}
    source_options=[]
    for item in items:
        sku=item["sku"]
        sources={a["search_id"] for a in adds if a["sku"]==sku}
        source_options.append(sources)
        searched=any(sku in s["result_skus"] for s in searches)
        added=sku in rows and rows[sku]["quantity"]==1 and rows[sku]["unit_price_paise"]==item["unit_price_paise"]
        stages["search_"+sku]={"completed":searched,"status":"PASS" if searched else "PENDING"}
        stages["cart_"+sku]={"completed":added,"status":"PASS" if added else "PENDING"}
    distinct_sources=all(source_options) and any(len(set(ids))==3 for ids in product(*source_options))
    checks={
        "three_distinct_expected_products":len(cart)==len(rows)==3 and set(rows)==set(expected),
        "quantities_and_prices_correct":all(stages["cart_"+i["sku"]]["completed"] for i in items),
        "three_separate_searches":bool(distinct_sources),
        "cart_is_open":state["screen"]=="CART",
        "currency_is_INR":state["currency"]=="INR",
        "counter_consistency":state["distinct_items"]==len(cart) and state["total_quantity"]==sum(r["quantity"] for r in cart),
        "line_totals_consistent":all(r["quantity"]>0 and r["line_total_paise"]==r["quantity"]*r["unit_price_paise"] for r in cart),
        "subtotal_consistent":state["subtotal_paise"]==sum(r["line_total_paise"] for r in cart),
        "exact_expected_subtotal":state["subtotal_paise"]==task["expected_subtotal_paise"],
    }
    passed=all(checks.values()) and all(s["completed"] for s in stages.values())
    return result("PASS" if passed else "FAIL","EXACT_THREE_ITEM_CART" if passed else "CART_TASK_INCOMPLETE_OR_MISMATCH",checks,stages)
