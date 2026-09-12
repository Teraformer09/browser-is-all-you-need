"""Fixed request/resource reservations, not outcome-dependent reward tuning."""
import base64
import json
from decimal import Decimal
from pathlib import Path

INPUT_LIMIT = 8000
OUTPUT_LIMIT = 2048
MAX_CALLS = 12 * 18
VM_RESERVE = Decimal("0.156")  # 4 CPU, 8 GB RAM, 32 GB disk, 30 minutes.
DEFAULT_MODEL = "openai/gpt-4.1"
DEFAULT_INPUT_USD = 2
DEFAULT_OUTPUT_USD = 8
DEFAULT_CAP = Decimal("9")


def call_reserve(input_usd=DEFAULT_INPUT_USD, output_usd=DEFAULT_OUTPUT_USD):
    return (Decimal(INPUT_LIMIT) * Decimal(str(input_usd)) +
            Decimal(OUTPUT_LIMIT) * Decimal(str(output_usd))) / 1000000


CALL_RESERVE = call_reserve()


def valid_model(value):
    import re
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9-]+/[a-z0-9._-]+", value) is None:
        raise ValueError("campaign_model must be a provider/model slug")
    return value


def campaign_plan(cap, completed_attempts=0, attempts_this_run=None, prior_spend_usd=0,
                  input_usd=DEFAULT_INPUT_USD, output_usd=DEFAULT_OUTPUT_USD, planned_attempts=12):
    """Validate a bounded continuation without creating files or billed resources."""
    if isinstance(cap, bool):
        raise ValueError("Explicit numeric campaign cap required")
    cap = Decimal(str(cap))
    if not cap.is_finite() or cap <= 0 or cap > DEFAULT_CAP:
        raise ValueError("Campaign cap must be positive and within the original USD 9 ceiling")
    if type(planned_attempts) is not int or not 1 <= planned_attempts <= 12:
        raise ValueError("planned_attempts must be an integer from one through twelve")
    if type(completed_attempts) is not int or not 0 <= completed_attempts < planned_attempts:
        raise ValueError("completed_attempts must be an integer within the planned series")
    limit = planned_attempts - completed_attempts if attempts_this_run is None else attempts_this_run
    if type(limit) is not int or not 1 <= limit <= planned_attempts - completed_attempts:
        raise ValueError("Continuation must fit the remaining planned-attempt slots")
    if type(prior_spend_usd) not in (int, float, Decimal):
        raise ValueError("prior_spend_usd must be a finite nonnegative number")
    prior = Decimal(str(prior_spend_usd))
    if not prior.is_finite() or prior < 0:
        raise ValueError("prior_spend_usd must be a finite nonnegative number")
    reserve = call_reserve(input_usd, output_usd)
    upper = prior + limit * VM_RESERVE + limit * 18 * reserve
    if upper > cap:
        raise ValueError("Continuation reservations exceed the approved campaign cap")
    return {"completed_attempts": completed_attempts, "attempt_limit": limit,
            "prior_spend": prior, "approved_run_upper_bound": upper,
            "input_usd": input_usd, "output_usd": output_usd, "planned_attempts": planned_attempts}


class CampaignBudget:
    def __init__(self, cap, output, *, completed_attempts=0, attempts_this_run=None, prior_spend_usd=0,
                 input_usd=DEFAULT_INPUT_USD, output_usd=DEFAULT_OUTPUT_USD, planned_attempts=12, model=DEFAULT_MODEL):
        plan = campaign_plan(cap, completed_attempts, attempts_this_run, prior_spend_usd,
                             input_usd=input_usd, output_usd=output_usd, planned_attempts=planned_attempts)
        self.completed_attempts, self.attempt_limit = plan["completed_attempts"], plan["attempt_limit"]
        self.prior_spend, self.run_upper_bound = plan["prior_spend"], plan["approved_run_upper_bound"]
        self.reserve = call_reserve(input_usd, output_usd)
        self.model, self.planned_attempts = valid_model(model), planned_attempts
        self.cap, self.path = Decimal(str(cap)), Path(output) / "campaign-budget.json"
        self.attempts = self.calls = 0
        self.stopped = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise RuntimeError("Campaign ledger already exists; do not duplicate or resume automatically")
        self.persist()

    def persist(self):
        value = {"cap_usd": float(self.cap), "attempts_reserved": self.attempts,
                 "requests_reserved": self.calls, "stopped": self.stopped,
                 "reserved_upper_bound_usd": float(self.prior_spend + self.attempts * VM_RESERVE + self.calls * self.reserve),
                 "complete_campaign_upper_bound_usd": float(self.run_upper_bound),
                 "prior_spend_usd": float(self.prior_spend),
                 "completed_attempts_before_run": self.completed_attempts,
                 "max_attempts_this_run": self.attempt_limit,
                 "campaign_attempt_number": self.completed_attempts + self.attempts,
                 "campaign_planned_attempts": self.planned_attempts,
                 "campaign_model": self.model,
                 "transport_retries": 0, "rollout_retries": 0}
        self.path.write_text(json.dumps(value, indent=2))
        return value

    def reserve_attempt(self):
        if self.stopped or self.attempts >= self.attempt_limit:
            raise RuntimeError("Campaign attempt/spending guard stopped additional VMs")
        self.attempts += 1
        return self.persist()

    def reserve_call(self):
        total = self.prior_spend + self.attempts * VM_RESERVE + (self.calls + 1) * self.reserve
        if self.stopped or not self.attempts or self.calls >= self.attempt_limit * 18 or total > self.cap:
            raise RuntimeError("Campaign request/spending guard stopped inference")
        self.calls += 1  # An ambiguous failed request remains reserved; never retried.
        return self.persist()


def as_dict(value):
    return value.model_dump(exclude_none=True) if hasattr(value, "model_dump") else value


def bounded_prompt(messages, actions):
    """Latest original screenshot + current UI + action-only history; no old images."""
    import tiktoken
    messages = [as_dict(m) for m in messages]
    system = next(m for m in messages if m["role"] == "system")
    latest = messages[-1]
    parts = [as_dict(p) for p in latest["content"]]
    observation = json.loads(next(p["text"] for p in parts if p["type"] == "text"))
    nodes = []
    for node in observation["ui"]:
        if node.get("id") or node.get("text") or node.get("description"):
            nodes.append({k: node[k] for k in ("id", "text", "description", "enabled", "clickable", "bounds") if k in node})
    observation["ui"] = nodes
    observation["previous_actions"] = actions
    text = json.dumps(observation, ensure_ascii=False, separators=(",", ":"))
    images = [p for p in parts if p["type"] == "image_url"]
    if len(images) != 1:
        raise ValueError("Exactly one current screenshot is required")
    image = as_dict(images[0]["image_url"])
    prefix = "data:image/png;base64,"
    if not image["url"].startswith(prefix):
        raise ValueError("Screenshot must be inline original PNG")
    png = base64.b64decode(image["url"][len(prefix):], validate=True)
    width, height = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
    if not png.startswith(b"\x89PNG\r\n\x1a\n") or (width, height) != (1080, 2400):
        raise ValueError("Unexpected screenshot geometry; cost reservation must be revalidated")
    # 4096 is a conservative image-token allowance for this exact geometry.
    # 512 reserves chat framing; o200k_base is GPT-4.1's text encoding.
    encoded = tiktoken.get_encoding("o200k_base").encode(str(system["content"]) + text, disallowed_special=())
    upper = len(encoded) + 512 + 4096
    if upper > INPUT_LIMIT:
        raise ValueError("Prompt exceeds frozen input allowance; no model request sent")
    image["detail"] = "high"
    return [system, {"role": "user", "content": [{"type": "text", "text": text},
            {"type": "image_url", "image_url": image}]}], upper
