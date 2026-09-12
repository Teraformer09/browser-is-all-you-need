import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request


def model_info(model, allow_paid=False, max_price_per_mtok=None):
    from decimal import Decimal
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        items = json.load(response)["data"]
    info = next((m for m in items if m["id"] == model), None)
    if not info:
        raise ValueError("Model not in the current OpenRouter catalog")
    if model.endswith(":free"):
        if any(Decimal(str(info["pricing"].get(k,"1"))) != 0 for k in ("prompt","completion")):
            raise ValueError("Model must currently have zero prompt/completion price and :free suffix")
    elif not (allow_paid and max_price_per_mtok is not None):
        raise ValueError("Paid models require allow_paid=True with an explicit price ceiling")
    else:
        for k in ("prompt","completion"):
            if Decimal(str(info["pricing"].get(k,"1"))) * Decimal(1000000) > Decimal(str(max_price_per_mtok)):
                raise ValueError("Model price exceeds the declared ceiling")
    if "image" not in info["architecture"]["input_modalities"]:
        raise ValueError("Selected model must support screenshot input")
    return info


def call_model(model, messages, temperature=0):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    payload = {"model":model,"messages":messages,"max_tokens":2048,"temperature":temperature,
               "response_format":{"type":"json_object"}}
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    retries = []
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request,timeout=60) as response:
                data = json.load(response)
            text = data["choices"][0]["message"].get("content")
            if not isinstance(text,str) or not text.strip():
                retries.append({"attempt":attempt+1,"empty_content":True})
                if attempt == 1:
                    # Some OpenRouter routes (minimax-m3) emit no content under
                    # json_object mode; the action schema is validated downstream.
                    payload = {k: v for k, v in payload.items() if k != "response_format"}
                    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                        data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
                if attempt == 3:
                    raise RuntimeError("Model returned no action text after bounded retries")
                time.sleep(10)
                continue
            receipt_extra = {"response_format_dropped": any(r.get("empty_content") for r in retries)}
            return {"role":"assistant","content":text}, {"id":data.get("id"),"model":data.get("model"),
                "usage":data.get("usage"),"finish_reason":data["choices"][0].get("finish_reason"),
                "http_retries":retries, **receipt_extra}
        except urllib.error.HTTPError as exc:
            retries.append({"attempt":attempt+1,"http_status":exc.code})
            if exc.code != 429 or attempt == 2:
                raise RuntimeError(f"OpenRouter HTTP {exc.code}; {attempt+1} transport attempts") from None
            time.sleep(20)
    raise RuntimeError("Model transport exhausted")
