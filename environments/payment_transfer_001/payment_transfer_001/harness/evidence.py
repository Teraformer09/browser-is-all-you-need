import csv
import hashlib
import io
import json
import re
import shlex
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from payment_transfer_001.harness.actions import PACKAGE


def stamp():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def nodes(xml):
    result = []
    for node in ET.fromstring(xml).iter("node"):
        a = node.attrib
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", a.get("bounds", ""))
        if a.get("package") == PACKAGE and bounds:
            result.append({"id": a.get("resource-id", "").removeprefix(PACKAGE + ":id/"),
                "text": a.get("text", ""), "description": a.get("content-desc", ""),
                "enabled": a.get("enabled") == "true", "clickable": a.get("clickable") == "true",
                "focused": a.get("focused") == "true", "class": a.get("class", ""),
                "bounds": list(map(int, bounds.groups()))})
    return result


def prefs_snapshot(xml):
    root = ET.fromstring(xml)
    values = [x.text for x in root if x.tag == "string" and x.get("name") == "snapshot"]
    if len(values) != 1:
        raise ValueError("Missing unique persisted snapshot")
    return json.loads(values[0])
