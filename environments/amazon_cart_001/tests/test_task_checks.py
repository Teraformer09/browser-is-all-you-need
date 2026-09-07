import copy
import json
from pathlib import Path
import unittest
from amazon_cart_001.verification.records import verify

TASK=json.loads((Path(__file__).parents[1]/"amazon_cart_001/specs/task.json").read_text())

def fixture():
    rows=[];searches=[];adds=[]
    for i,item in enumerate(TASK["expected_items"],1):
        rows.append({"sku":item["sku"],"name":item["name"],"quantity":1,"unit_price_paise":item["unit_price_paise"],"line_total_paise":item["unit_price_paise"]})
        searches.append({"search_id":i,"query":item["query"],"result_skus":[item["sku"]]})
        adds.append({"sku":item["sku"],"search_id":i,"query":item["query"],"quantity_after":1})
    return {"schema_version":1,"episode_id":"test","simulated":True,"screen":"CART","currency":"INR","revision":10,
            "distinct_items":3,"total_quantity":3,"subtotal_paise":499700,"cart_items":rows,"searches":searches,"additions":adds}

class VerifierTests(unittest.TestCase):
    def test_correct_three_item_cart(self):
        r=verify(fixture(),TASK,"test");self.assertEqual(r["status"],"PASS");self.assertEqual(r["completed_stages"],6)
    def test_wrong_product_fails(self):
        s=fixture();s["cart_items"][0]["sku"]="headphones_wired_001"
        self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_duplicate_quantity_fails(self):
        s=fixture();s["cart_items"][0]["quantity"]=2
        self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_extra_item_fails(self):
        s=fixture();s["cart_items"].append(copy.deepcopy(s["cart_items"][0]))
        self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_missing_item_fails(self):
        s=fixture();s["cart_items"].pop()
        self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_cart_must_be_open(self):
        s=fixture();s["screen"]="BROWSE";self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_wrong_total_fails(self):
        s=fixture();s["subtotal_paise"]+=1;self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_empty_evidence_invalid(self):
        self.assertEqual(verify({},TASK,"test")["status"],"INVALID")
    def test_stale_episode_invalid(self):
        self.assertEqual(verify(fixture(),TASK,"stale")["status"],"INVALID")
    def test_missing_search_record_invalid(self):
        s=fixture();s["searches"].pop();self.assertEqual(verify(s,TASK,"test")["status"],"INVALID")
    def test_add_not_in_search_result_invalid(self):
        s=fixture();s["searches"][0]["result_skus"]=[]
        self.assertEqual(verify(s,TASK,"test")["status"],"INVALID")
    def test_single_search_does_not_meet_three_search_requirement(self):
        s=fixture();s["searches"]=[{"search_id":1,"query":"demo","result_skus":[i["sku"] for i in TASK["expected_items"]]}]
        for a in s["additions"]:a.update(search_id=1,query="demo")
        self.assertEqual(verify(s,TASK,"test")["status"],"FAIL")
    def test_fractional_quantity_invalid(self):
        s=fixture();s["cart_items"][0]["quantity"]=1.5
        self.assertEqual(verify(s,TASK,"test")["status"],"INVALID")
    def test_task_total_mismatch_invalid(self):
        task=copy.deepcopy(TASK);task["expected_subtotal_paise"]=1
        self.assertEqual(verify(fixture(),task,"test")["status"],"INVALID")
    def test_scripted_records_never_training_eligible(self):
        self.assertFalse(verify(fixture(),TASK,"test")["training_eligible"])
    def test_search_progress_before_add(self):
        s=fixture();s["cart_items"]=[];s["additions"]=[]
        s.update(subtotal_paise=0,distinct_items=0,total_quantity=0,screen="BROWSE")
        self.assertEqual(verify(s,TASK,"test")["completed_stages"],3)

if __name__=="__main__":unittest.main()
