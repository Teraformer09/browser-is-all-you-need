import copy
import json
import unittest
from amazon_improved_task_001.harness.actions import schema_error
from amazon_improved_task_001.harness.peach import permission_error,target_node,ui_nodes,PACKAGE
from amazon_improved_task_001.verification.peach import replay,snapshot,task_spec,cart_complete,endpoint,progress
from amazon_improved_task_001.verification.contracts import Unassessable

EPISODE="peach_"+"a"*32

def fixture():
    products=[{"id":i+1,"sku":p["sku"],"name":p["name"],"category":"Electronics",
        "price_paise":p["unit_price_paise"]} for i,p in enumerate(task_spec()["expected_items"])]
    tables={"products":products,"cart":[],"search_history":[],
        "eval_session":[{"singleton":1,"episode_id":EPISODE,"page":"home","draft":"","query":""}],"eval_events":[]}
    def event(kind,payload):
        tables["eval_events"].append({"sequence":len(tables["eval_events"]),"kind":kind,"payload":json.dumps(payload)})
    event("reset",{"episode_id":EPISODE})
    for p in products:
        event("viewport",{"page":"results","draft":p["name"],"query":p["name"]})
        event("search",{"query":p["name"]})
        event("add",{"product_id":p["id"],"quantity_after":1})
        tables["cart"].append({"product_id":p["id"],"qty":1})
    event("viewport",{"page":"cart","draft":products[-1]["name"],"query":products[-1]["name"]})
    tables["eval_session"][0].update(page="cart",draft=products[-1]["name"],query=products[-1]["name"])
    return tables

class PeachTests(unittest.TestCase):
    def test_correct_cart(self):
        state=snapshot(fixture(),EPISODE)
        self.assertTrue(cart_complete(state,task_spec()))
        self.assertEqual(progress(state,task_spec())["completed_stages"],6)
    def test_wrong_quantity(self):
        tables=fixture()
        event={"sequence":len(tables["eval_events"]),"kind":"add","payload":json.dumps({"product_id":1,"quantity_after":2})}
        tables["eval_events"].append(event);tables["cart"][0]["qty"]=2
        self.assertFalse(cart_complete(snapshot(tables,EPISODE),task_spec()))
    def test_missing_search_is_failure_not_invalid(self):
        tables=fixture()
        for event in tables["eval_events"]:
            if event["kind"]=="search":
                event["kind"]="viewport";event["payload"]=json.dumps({"page":"home","draft":"","query":""})
        state=snapshot(tables,EPISODE)
        self.assertFalse(endpoint("T4",state,task_spec()))
    def test_cannot_count_none_as_distinct_search(self):
        tables=fixture()
        e=tables["eval_events"][2]
        e.update(kind="viewport",payload=json.dumps({"page":"results","draft":"","query":""}))
        self.assertFalse(endpoint("T4",snapshot(tables,EPISODE),task_spec()))
    def test_not_opened_cart(self):
        tables=fixture()
        tables["eval_session"][0]["page"]="results"
        last=json.loads(tables["eval_events"][-1]["payload"]);last["page"]="results"
        tables["eval_events"][-1]["payload"]=json.dumps(last)
        self.assertFalse(endpoint("T6",snapshot(tables,EPISODE),task_spec()))
    def test_missing_event(self):
        tables=fixture();tables["eval_events"].pop(2)
        with self.assertRaises(Unassessable): snapshot(tables,EPISODE)
    def test_mutation_disagrees_with_cart(self):
        tables=fixture();tables["cart"][0]["qty"]=3
        with self.assertRaises(Unassessable): snapshot(tables,EPISODE)
    def test_stale_episode(self):
        with self.assertRaises(Unassessable): snapshot(fixture(),"peach_"+"b"*32)
    def test_nonobject_actions(self):
        for value in (None,[],42,True,"tap"):
            self.assertIsNotNone(schema_error(value))
            self.assertIsNotNone(permission_error(value))
    def test_unsupported_product(self):
        self.assertIsNotNone(permission_error({"type":"tap_element","element_id":"add_DC999"}))
    def test_duplicate_target_rejected(self):
        node={"id":"add_DC001","enabled":True,"clickable":True,"class":"Button","bounds":[0,0,40,40]}
        with self.assertRaises(ValueError):
            target_node({"type":"tap_element","element_id":"add_DC001"},[node,node])
    def test_real_package_alias(self):
        xml=('<hierarchy><node package="'+PACKAGE+'" resource-id="'+PACKAGE+
            ':id/etSearchBox" bounds="[0,0][100,50]" enabled="true" clickable="true" class="android.widget.AutoCompleteTextView"/></hierarchy>').encode()
        self.assertEqual(ui_nodes(xml,[]) [0]["id"],"search_input")
    def test_empty_cart_is_assessable(self):
        tables=fixture()
        tables["cart"]=[];tables["eval_events"]=tables["eval_events"][:1]
        tables["eval_session"][0].update(page="home",draft="",query="")
        self.assertFalse(cart_complete(snapshot(tables,EPISODE),task_spec()))

if __name__=="__main__": unittest.main()
