"""Bounded HTTP 429 retries; preserve actor requests and never select paid models."""
import json
import re
import time
import urllib.error
import urllib.request


def request_completion(request, *, max_attempts=3, opener=None, sleeper=None):
    opener = opener or urllib.request.urlopen
    sleeper = sleeper or time.sleep
    retries = []
    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=60) as response:
                return json.load(response), retries
        except urllib.error.HTTPError as error:
            body = error.read(4096).decode("utf-8", errors="replace")
            body = re.sub(r"(?:pit_|ghp_|sk-or-v1-)[A-Za-z0-9_-]+", "[REDACTED]", body)
            record = {"attempt": attempt, "http_status": error.code, "error": body[:1000]}
            if error.code != 429 or attempt == max_attempts:
                print("MODEL_HTTP_ERROR=" + json.dumps(record), flush=True)
                raise RuntimeError(f"OpenRouter HTTP {error.code} after {attempt} attempt(s): {body[:1000]}") from error
            try:
                delay = min(60.0, max(20.0, float(error.headers.get("Retry-After", 30 * attempt))))
            except (ValueError, TypeError, AttributeError):
                delay = min(60.0, 30.0 * attempt)
            record["retry_after_seconds"] = delay
            retries.append(record)
            print("MODEL_HTTP_RETRY=" + json.dumps(record), flush=True)
            sleeper(delay)
    raise RuntimeError("No model HTTP attempt was configured")

import argparse
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from uber_clone_031.harness.device import TracedAdbDevice
from uber_clone_031.harness.episode import RideStageEnv
from uber_clone_031.harness.backend.task_specs import build_known_task, load_task_spec
from uber_clone_031.harness.evidence import EvidenceEnv, write_json
from uber_clone_031.verification.records import RUBRIC_VERSION
from uber_clone_031.verification.registry import load_registry
from uber_clone_031.agents.openrouter import request_completion
from uber_clone_031.harness.actions import ACTION_SCHEMA, completion_payload

def model_action(model, messages, response_format="text"):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    if not model.endswith(":free"):
        raise ValueError("This runner only authorizes OpenRouter :free models")
    payload = completion_payload(model, messages, response_format)
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + key,
        "Content-Type": "application/json"})
    data, http_retries = request_completion(request)
    message = data["choices"][0]["message"]
    content = message.get("content") or ""
    if not content.strip():
        raise RuntimeError("Model returned no action content")
    return {"role": "assistant", "content": content}, {"id": data.get("id"),
        "model": data.get("model"), "usage": data.get("usage"),
        "finish_reason": data["choices"][0].get("finish_reason"), "http_retries": http_retries}
