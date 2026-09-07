"""Six diagnostic stages: search and cart inclusion for each requested product."""
from amazon_cart_001.verification.records import verify

def progress(snapshot, task):
    outcome = verify(snapshot, task, snapshot.get("episode_id") if isinstance(snapshot, dict) else None)
    return {"completed_stages": outcome["completed_stages"], "total_stages": 6,
            "stages": outcome["stages"], "diagnostic_only": True}
