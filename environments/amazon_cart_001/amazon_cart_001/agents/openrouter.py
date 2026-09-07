import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request


def model_info(model):
    from decimal import Decimal
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        items = json.load(response)["data"]
    info = next((m for m in items if m["id"] == model), None)
    if not info or not model.endswith(":free") or any(Decimal(str(info["pricing"].get(k,"1"))) != 0 for k in ("prompt","completion")):
        raise ValueError("Model must currently have zero prompt/completion price and :free suffix")
    if "image" not in info["architecture"]["input_modalities"]:
        raise ValueError("Selected model must support screenshot input")
    return info


def call_model(model, messages):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    payload = {"model":model,"messages":messages,"max_tokens":2048,"temperature":0,
               "response_format":{"type":"json_object"}}
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    retries = []
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                data = json.load(response)
            text = data["choices"][0]["message"].get("content")
            if not isinstance(text,str) or not text.strip():
                raise RuntimeError("Model returned no action text")
            return {"role":"assistant","content":text}, {"id":data.get("id"),"model":data.get("model"),
                "usage":data.get("usage"),"finish_reason":data["choices"][0].get("finish_reason"),
                "http_retries":retries}
        except urllib.error.HTTPError as exc:
            retries.append({"attempt":attempt+1,"http_status":exc.code})
            if exc.code != 429 or attempt == 2:
                raise RuntimeError(f"OpenRouter HTTP {exc.code}; {attempt+1} transport attempts") from None
            time.sleep(20)
    raise RuntimeError("Model transport exhausted")
