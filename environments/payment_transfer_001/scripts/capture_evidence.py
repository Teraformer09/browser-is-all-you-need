"""Read a running payment demo; never launch it, act for the model, or upload."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from payment_transfer_001.verification.records import verify, verdict

PACKAGE = "com.primeintellect.paymentdemo"

def capture(serial, episode_id, output, adb="adb"):
    root = Path(output) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    root.mkdir(parents=True, exist_ok=False)
    receipts = []
    def command(*args):
        result = subprocess.run([adb, "-s", serial, *args], capture_output=True, timeout=30)
        receipts.append({"args": args, "returncode": result.returncode,
                         "captured_at": datetime.now(timezone.utc).isoformat(),
                         "stderr": result.stderr.decode(errors="replace")})
        result.check_returncode()
        return result.stdout
    def snapshot():
        raw = command("shell", "content", "query", "--uri", "content://" + PACKAGE + ".verifier/state")
        text = raw.decode()
        if "snapshot=" not in text:
            raise ValueError("Read-only provider did not return a snapshot")
        return json.loads(text.split("snapshot=", 1)[1].strip())
    def save(name, data):
        (root / name).write_bytes(data)
    temp = "/sdcard/paymentdemo-ui-" + uuid4().hex + ".xml"
    result = verdict("INVALID", "CAPTURE_NOT_COMPLETED")
    try:
        before = snapshot()
        save("provider_before.json", json.dumps(before, indent=2).encode())
        command("shell", "uiautomator", "dump", temp)
        ui = command("exec-out", "cat", temp)
        save("ui.xml", ui)
        if not any(node.get("package") == PACKAGE for node in ET.fromstring(ui).iter("node")):
            raise ValueError("Payment app is not present in current UI evidence")
        png = command("exec-out", "screencap", "-p")
        if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) < 33:
            raise ValueError("Invalid screenshot")
        save("screen.png", png)
        after = snapshot()
        save("provider_after.json", json.dumps(after, indent=2).encode())
        if before != after:
            raise ValueError("App changed during capture; retry after it is stable")
        save("snapshot.json", json.dumps(after, indent=2).encode())
        task = json.loads((Path(__file__).resolve().parents[1] / "payment_transfer_001/specs/task.json").read_text())
        result = verify(after, task, episode_id)
    except Exception as ex:
        result = verdict("INVALID", "EVIDENCE_COLLECTION_FAILED")
        save("error.json", json.dumps({"type": type(ex).__name__, "message": str(ex)}).encode())
    finally:
        try:
            command("shell", "rm", "-f", temp)
        except Exception:
            pass
    # Inspection/smoke-test evidence is not an agent training rollout.
    result = {**result, "training_eligible": False, "capture_only": True}
    save("capture_receipts.json", json.dumps(receipts, indent=2).encode())
    save("verdict.json", json.dumps(result, indent=2).encode())
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file()}
    save("manifest.json", json.dumps({"episode_id":episode_id, "files":manifest, "model_calls":0,
         "actor_actions":0, "capture_only":True,
         "verifier_sha256":hashlib.sha256((Path(__file__).resolve().parents[1] / "payment_transfer_001/verification/records.py").read_bytes()).hexdigest(),
         "collector_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2).encode())
    return root, result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", required=True)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--adb", default="adb")
    args = parser.parse_args()
    root, result = capture(args.serial, args.episode_id, args.output, args.adb)
    print(json.dumps({"directory":str(root), **result}))
    raise SystemExit(2 if result["status"] == "INVALID" else 0)
