"""Deterministic screenshot OCR receipts; no LLM calls or pixel editing."""
import csv
import io
import re
import subprocess
import xml.etree.ElementTree as ET


def capture_ocr(path, screenshot_hash, ui_xml):
    result = subprocess.run(["tesseract", str(path), "stdout", "--psm", "11", "tsv"],
                            check=True, capture_output=True, text=True, timeout=25)
    boxes = []
    for node in ET.fromstring(ui_xml).iter("node"):
        if node.get("resource-id", "").rsplit("/", 1)[-1] in {"route_summary_text", "ride_progress_text", "final_status_text"}:
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
            if bounds: boxes.append(tuple(map(int, bounds.groups())))
    words = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        if not row.get("text", "").strip(): continue
        x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        if any(l <= x + w/2 <= r and t <= y + h/2 <= b for l,t,r,b in boxes):
            words.append({"text": row["text"], "confidence": float(row["conf"]),
                          "bounds": [x,y,x+w,y+h]})
    return {"engine":"tesseract", "psm":11, "source_sha256":screenshot_hash,
            "text":" ".join(word["text"] for word in words), "words":words,
            "min_confidence":min((word["confidence"] for word in words), default=0),
            "regions":boxes, "stderr":result.stderr}
