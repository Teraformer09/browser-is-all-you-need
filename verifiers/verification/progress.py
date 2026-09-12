"""Six diagnostic stages and weighted partial progress.

The stage result is separate from terminal verifier reward.
"""

SEARCH_STAGE_WEIGHT = 0.5
CART_STAGE_WEIGHT = 0.8
STAGE_SCORE_DIVISOR = 3.0

def weighted_stage_result(stages):
    stages = stages or []
    passed_search = sum(bool(s.get("complete")) and (".searched" in s.get("id", "") or s.get("id", "").startswith("search_")) for s in stages)
    passed_cart = sum(bool(s.get("complete")) and (".in_cart" in s.get("id", "") or s.get("id", "").startswith("cart_")) for s in stages)
    value = (SEARCH_STAGE_WEIGHT * passed_search + CART_STAGE_WEIGHT * passed_cart) / STAGE_SCORE_DIVISOR
    return {"passed_search_stages": passed_search, "passed_cart_stages": passed_cart, "search_stage_weight": SEARCH_STAGE_WEIGHT, "cart_stage_weight": CART_STAGE_WEIGHT, "divisor": STAGE_SCORE_DIVISOR, "value": round(value, 10)}
def progress(snapshot, task):
    from amazon_cart_001.verification.records import verify
    outcome = verify(snapshot, task, snapshot.get("episode_id") if isinstance(snapshot, dict) else None)
    return {"completed_stages": outcome["completed_stages"], "total_stages": 6,
            "stages": outcome["stages"], "stage_result": weighted_stage_result(outcome["stages"]), "final_result": weighted_stage_result(outcome["stages"])["value"], "diagnostic_only": True}
