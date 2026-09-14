#!/usr/bin/env python3
"""Black-box developer UI checks on a dedicated emulator. No agent, rubric or reward.

Use only on the disposable emulator for this app; actions deliberately populate
its local cart. XML, PNG and this script's output are development evidence.
"""
import argparse
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--adb", required=True)
parser.add_argument("--port", required=True)
parser.add_argument("--serial", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--start", choices=("all", "after_cart"), default="all")
args = parser.parse_args()
out = args.output.resolve()
if not str(out).startswith("/data/Tirtha/"):
    raise SystemExit("All output must stay under /data/Tirtha")
out.mkdir(parents=True, exist_ok=True)
adb = [args.adb, "-P", args.port, "-s", args.serial]
checks = 0

def call(*parts, binary=False):
    result = subprocess.run(adb + list(parts), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
    return result.stdout if binary else result.stdout.decode()

def tree():
    # Fresh successful dump only: never accept a previous XML file after failure.
    for attempt in range(4):
        receipt = call("shell", "uiautomator", "dump", "/sdcard/democart-check.xml")
        if "dumped to:" in receipt:
            raw = call("exec-out", "cat", "/sdcard/democart-check.xml")
            return ET.fromstring(raw), raw
        time.sleep(0.25)
    raise AssertionError("No fresh UI hierarchy")

def node(value, attribute="content-desc"):
    root, _ = tree()
    for n in root.iter("node"):
        if (n.get(attribute, "").casefold() == value.casefold() if attribute == "text" else n.get(attribute) == value):
            return n
    raise AssertionError(f"Missing UI target: {attribute}={value}")

def tap(value, attribute="content-desc"):
    n = node(value, attribute)
    bounds = list(map(int, re.findall(r"\d+", n.get("bounds", ""))))
    assert len(bounds) == 4 and bounds[2] > bounds[0] and bounds[3] > bounds[1], (value, bounds)
    call("shell", "input", "tap", str((bounds[0] + bounds[2]) // 2), str((bounds[1] + bounds[3]) // 2))

def has(value):
    global checks
    root, _ = tree()
    assert any(value in (n.get("text", "") + " " + n.get("content-desc", "")) for n in root.iter("node")), value
    checks += 1
    print(f"OK {checks}: {value}", flush=True)

def shot(name):
    _, raw = tree()
    (out / f"{name}.xml").write_text(raw)
    (out / f"{name}.png").write_bytes(call("exec-out", "screencap", "-p", binary=True))

def text_input(value):
    call("shell", "input", "keycombination", "113", "29")
    call("shell", "input", "text", value.replace(" ", "%s"))

def search(value):
    tap("com.primeintellect.amazonuidemo:id/etSearchBox", "resource-id")
    text_input(value)
    call("shell", "input", "keyevent", "66")
    has("Results for")

def back():
    call("shell", "input", "keyevent", "4")

def bottom(label):
    root, _ = tree()
    target = next(n.get("content-desc") for n in root.iter("node") if n.get("content-desc", "").startswith(label + " tab"))
    tap(target)

if args.start == "all":
    has("BIG-SCREEN MOMENTS")
    shot("home")
    tap("Show promotion 2")
    has("TUNE INTO SOMETHING GOOD")
    tap("Show promotion 1")
    tap("Featured deal: Nimbus Vision 55-inch QLED TV; tap for details, swipe for next offer")
    has("Product code: DC007")
    has("Cart tab, 0 items")  # A banner tap is not an add-to-cart.
    back()

    for q, name in [
        ("Nimbus Wireless Headphones", "Nimbus Wireless Headphones"),
        ("Trail Steel Water Bottle", "Trail Steel Water Bottle"),
        ("Metro Laptop Backpack", "Metro Laptop Backpack"),
    ]:
        search(q)
        tap("Add " + name + " to cart")
    has("Cart tab, 3 items")
    shot("search")
    bottom("Cart")
    has("Subtotal (3 items): ₹4,997")
    shot("cart")
    tap("Increase quantity of Nimbus Wireless Headphones")
    has("Subtotal (4 items): ₹7,496")
    tap("Decrease quantity of Nimbus Wireless Headphones")
    has("Subtotal (3 items): ₹4,997")
    tap("Review demo cart")
    has("No order is placed")
    shot("cart-review")
tap("Back to cart", "text")

bottom("Wallet")
has("SIMULATED BALANCE")
tap("Add 500 simulated wallet credits")
has("₹1,750")
shot("wallet")
bottom("You")
has("Metro Laptop Backpack")
tap("Choose delivery location")
tap("Office · New Delhi 110002", "text")
has("New Delhi 110002")
shot("profile-history")

bottom("Menu")
has("Shop by category")
shot("menu")
tap("Browse Fresh")
has("Fresh Orchard Fruit Basket")
bottom("Rufus")
has("not Amazon's AI")
shot("assistant")

# All device-dependent triggers have deterministic manual fallbacks.
tap("Voice search")
tap("Type instead", "text")
tap("headphones", "text")  # EditText hint
text_input("Bottle")
tap("Apply", "text")
has("Trail Steel Water Bottle")
tap("Lens demo: camera or manual matching")
tap("Choose category", "text")
tap("Backpack", "text")
has("Metro Laptop Backpack")
tap("Scan or enter a demo product code")
tap("Enter code", "text")
tap("DC001", "text")
text_input("BAD")
tap("Apply", "text")
has("Unknown demo code")
text_input("DC003")
tap("Apply", "text")
has("Product code: DC003")
shot("product")

# Force-stop/relaunch checks real SQLite persistence, not only a cached counter.
call("shell", "am", "force-stop", "com.primeintellect.amazonuidemo")
call("shell", "am", "start", "-W", "-n", "com.primeintellect.amazonuidemo/.MainActivity")
has("New Delhi 110002")
bottom("Cart")
has("Subtotal (3 items): ₹4,997")
shot("cart-restored")
bottom("Wallet")
has("₹1,750")
bottom("You")
has("Bottle")
bottom("Home")
shot("home-final")
print(f"Developer UI checks complete: {checks}. No evaluation or model calls.", flush=True)
