"""Unscored live display operations for the private Prime Android worker.

Evaluation workers can capture frames, but reject every human control. Manual
control is enabled only by the separate inspection-mode worker startup flag.
"""
import argparse
import base64
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from amazon_cart_001.harness.hosted_worker import check_root, file_receipt, write_json
from amazon_cart_001.harness.peach import PeachDevice


def state(root):
    value = json.loads((root / "viewer_state.json").read_text())
    if value.get("running") is not True:
        raise RuntimeError("VIEWER_SESSION_CLOSED")
    return value


def capture(root, device=None):
    session = state(root)
    device = device or PeachDevice("emulator-5556")
    data = device.command("exec-out", "screencap", "-p", timeout=10)
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or not 33 <= len(data) <= 8 * 1024 * 1024:
        raise ValueError("INVALID_LIVE_PNG")
    width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if not 1 <= width <= 8192 or not 1 <= height <= 8192:
        raise ValueError("INVALID_LIVE_DIMENSIONS")
    directory = root / "live"
    directory.mkdir(exist_ok=True)
    frame_id = uuid4().hex
    destination = directory / (frame_id + ".png")
    destination.write_bytes(data)
    frame = {**file_receipt(destination), "frame_id": frame_id, "width": width, "height": height,
             "captured_at": time.time(), "episode_id": session["episode_id"],
             "interactive": session.get("inspection") is True}
    write_json(directory / (frame_id + ".json"), frame)
    # Keep eight recent frame pairs. This directory contains viewer captures only.
    metadata = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in metadata[8:]:
        if re.fullmatch(r"[a-f0-9]{32}\.json", path.name):
            path.with_suffix(".png").unlink(missing_ok=True)
            path.unlink()
    return frame


def control(root, payload, device=None):
    session = state(root)
    if session.get("inspection") is not True:
        raise PermissionError("READ_ONLY_EVALUATION: human control is disabled")
    if not isinstance(payload, dict) or not isinstance(payload.get("frame_id"), str):
        raise ValueError("Invalid control request")
    frame_id = payload["frame_id"]
    if re.fullmatch(r"[a-f0-9]{32}", frame_id) is None:
        raise ValueError("Invalid frame identity")
    frame = json.loads((root / "live" / (frame_id + ".json")).read_text())
    if frame["episode_id"] != session["episode_id"] or not 0 <= time.time() - frame["captured_at"] <= 5:
        raise ValueError("STALE_CONTROL_FRAME: refresh before interacting")
    kind = payload.get("type")
    expected_keys = {"tap": {"frame_id", "type", "x", "y"},
                     "swipe": {"frame_id", "type", "x1", "y1", "x2", "y2"},
                     "back": {"frame_id", "type"}, "text": {"frame_id", "type", "text"}}
    if kind not in expected_keys or set(payload) != expected_keys[kind]:
        raise ValueError("Unsupported control schema")
    for key in ("x", "y", "x1", "y1", "x2", "y2"):
        if key in payload:
            limit = frame["width"] if key.startswith("x") else frame["height"]
            if type(payload[key]) is not int or not 0 <= payload[key] < limit:
                raise ValueError("Coordinates outside displayed frame")
    device = device or PeachDevice("emulator-5556")
    if kind == "tap":
        device.command("shell", "input", "tap", str(payload["x"]), str(payload["y"]))
    elif kind == "swipe":
        device.command("shell", "input", "swipe", *[str(payload[k]) for k in ("x1", "y1", "x2", "y2")], "400")
    elif kind == "text":
        text = payload["text"]
        if not isinstance(text, str) or re.fullmatch(r"[A-Za-z0-9 ._-]{1,120}", text) is None:
            raise ValueError("Use 1-120 supported ASCII search characters")
        device.command("shell", "input", "text", text.replace(" ", "%s"))
    else:
        # Do not exit the controlled app into the Android launcher.
        current = device.runtime()["eval_session"]
        if not current or current[0].get("page") == "home":
            raise ValueError("Back from the app home screen is disabled")
        device.command("shell", "input", "keyevent", "KEYCODE_BACK")
    receipt = {"kind": "manual_ui_inspection", "evaluation": False,
               "at": time.time(), "episode_id": session["episode_id"], "control": payload}
    with (root / "viewer-controls.log").open("a") as stream:
        stream.write(json.dumps(receipt) + "\n")
    return {"accepted": True, "kind": "manual_ui_inspection", "evaluation": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["capture", "control"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--payload")
    args = parser.parse_args()
    root = check_root(args.root)
    if args.operation == "capture":
        value = capture(root)
    else:
        if not args.payload or len(args.payload) > 4096:
            parser.error("A bounded control payload is required")
        value = control(root, json.loads(base64.b64decode(args.payload, validate=True)))
    print(json.dumps(value))


if __name__ == "__main__":
    main()
