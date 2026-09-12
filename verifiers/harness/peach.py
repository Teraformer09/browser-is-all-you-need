"""Device and evidence adapter for the peach Java/XML/SQLite DemoCart UI.

This profile never redirects to the original shoppingdemo APK. The actor sees
only the visible hierarchy and screenshot, not the SQL or verifier answers.
"""
import json
import re
import shlex
import sqlite3
import time
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET

from amazon_cart_001.harness.device import Device
from amazon_cart_001.harness.actions import schema_error
from amazon_cart_001.harness.evidence import digest, save, stamp

PACKAGE = "com.primeintellect.amazonuidemo"
PROFILE = "peach_sqlite_v1"
TABLES = {"products":"id", "cart":"product_id", "search_history":"query COLLATE BINARY",
          "eval_session":"singleton", "eval_events":"sequence"}
SKUS = {f"DC{i:03d}" for i in range(1,10)}
CART_TARGETS = {"cart_button", "detail_cart_button"}
TARGETS = {"search_input", "search_button", "continue_shopping_button"} | CART_TARGETS | {
    prefix + sku for prefix in ("add_", "increase_", "decrease_", "remove_", "view_") for sku in SKUS}


def permission_error(action):
    error = schema_error(action)
    if error:
        return error
    target = action.get("element_id")
    if target is not None and target not in TARGETS:
        return "Target is not in this task's declared controls"
    if action["type"] == "type_text" and (target != "search_input" or
            re.fullmatch(r"[A-Za-z0-9 ._-]*", action["text"]) is None):
        return "Type only supported search text into search_input"
    return None


def database_tables(data):
    if not data.startswith(b"SQLite format 3\x00"):
        raise ValueError("Not a SQLite database")
    with sqlite3.connect(":memory:") as db:
        db.deserialize(data)
        db.execute("PRAGMA query_only=ON")
        db.row_factory = sqlite3.Row
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        return {table:[dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}")]
                for table,order in TABLES.items()}


def ui_nodes(xml, products):
    names = {p["name"]:p["sku"] for p in products}
    output = []
    for n in ET.fromstring(xml).iter("node"):
        a = n.attrib
        if a.get("package") != PACKAGE:
            continue
        bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", a.get("bounds", ""))
        if not bounds:
            continue
        resource = a.get("resource-id", "").removeprefix(PACKAGE + ":id/")
        description = a.get("content-desc", "")
        target = {"etSearchBox":"search_input", "btnSearch":"search_button"}.get(resource, "")
        if description.startswith("Cart tab"):
            target = "cart_button"
        elif description == "Go to cart":
            target = "detail_cart_button"
        elif description == "Home tab":
            target = "continue_shopping_button"
        for name,sku in names.items():
            for phrase,prefix in (("Add "+name+" to cart","add_"), ("Increase quantity of "+name,"increase_"),
                                  ("Decrease quantity of "+name,"decrease_"), ("Delete "+name,"remove_"),
                                  ("View "+name,"view_")):
                if description == phrase:
                    target = prefix + sku
        output.append({"id":target, "resource_id":a.get("resource-id", ""), "text":a.get("text", ""),
            "description":description, "enabled":a.get("enabled")=="true", "clickable":a.get("clickable")=="true",
            "focused":a.get("focused")=="true", "class":a.get("class", ""), "bounds":list(map(int,bounds.groups()))})
    return output


def target_node(action, ui):
    if action["type"] not in {"tap_element", "type_text"}:
        return None
    matches = [n for n in ui if n["id"] == action["element_id"] and n["enabled"] and
               n["bounds"][2] > n["bounds"][0] and n["bounds"][3] > n["bounds"][1] and
               (n["clickable"] or "EditText" in n["class"] or "AutoCompleteTextView" in n["class"])]
    if len(matches) != 1:
        raise ValueError("Target must resolve to exactly one visible, enabled control; scroll if needed")
    return matches[0]


class TextInputUnconfirmed(RuntimeError):
    """Input was dispatched, but the harness cannot confirm complete delivery."""


class PeachDevice(Device):
    input_readback_contract = "persisted_text_chars_v2"
    focus_probes = []

    def confirm_focus(self, element_id, deadline):
        # After the focus tap, the IME/input connection lags on slow TCG guests;
        # early characters vanish silently. Confirm the target reports
        # focused=true via bounded read-only dumps before any character goes out.
        resource = {"search_input": "etSearchBox"}.get(element_id)
        if resource is None:
            raise TextInputUnconfirmed("focus: unknown text target")
        for attempt in range(5):
            remaining = deadline - time.monotonic()
            if remaining <= 5:
                break
            index = len(self.trace)
            try:
                xml = self.ui()
                nodes = ui_nodes(xml, [])
                node = next((n for n in nodes if n.get("resource_id", "").endswith(":id/" + resource)), None)
                focused = bool(node and node.get("focused"))
                self.focus_probes.append({"trace_index": index + 1, "focused": focused,
                                          "episode_id": None, "raw": xml})
                if focused:
                    time.sleep(2)  # IME connection still trails the focus flag.
                    return
            except Exception as error:
                self.focus_probes.append({"trace_index": index, "focused": False,
                                          "error": type(error).__name__ + ": " + str(error)[:200], "raw": b""})
            time.sleep(min(3, max(0, deadline - time.monotonic())))
        raise TextInputUnconfirmed("focus: text field never reported focused; no characters were sent")

    def runtime(self, timeout=30):
        self.last_runtime_response = self.command("shell", "content", "query", "--uri",
            "content://"+PACKAGE+".verifier/state", timeout=timeout)
        raw = self.last_runtime_response.decode()
        if "snapshot=" not in raw:
            raise RuntimeError("Read-only SQLite provider unavailable")
        return json.loads(raw.split("snapshot=",1)[1].strip())

    def ui(self):
        # Retry only an explicitly empty UI root, never an Android input action.
        for attempt in range(3):
            remote = "/sdcard/peach-ui-"+uuid4().hex+".xml"
            try:
                result = self.command("shell", "uiautomator", "dump", remote, timeout=60).decode()
                if "dumped to:" not in result:
                    empty = (not result and self.trace[-1].get("stderr", "").strip() ==
                             "ERROR: null root node returned by UiTestAutomationBridge.")
                    if empty and attempt < 2:
                        continue
                    raise RuntimeError("UI dump did not complete")
                data = self.command("exec-out", "cat", remote)
                ET.fromstring(data)
                return data
            finally:
                self.command("shell", "rm", "-f", remote)

    def installed(self, apk):
        paths = self.command("shell", "pm", "path", PACKAGE).decode().splitlines()
        if len(paths)!=1 or not paths[0].startswith("package:/data/app/") or not paths[0].endswith("/base.apk"):
            raise RuntimeError("Unexpected installed APK path")
        actual = self.command("shell", "sha256sum", paths[0][8:]).decode().split()[0]
        expected = digest(Path(apk).read_bytes())
        if actual != expected:
            raise RuntimeError("Installed APK does not match selected peach build")
        return {"package":PACKAGE, "sha256":actual, "expected_sha256":expected, "path":paths[0][8:]}

    def start(self, episode):
        if re.fullmatch(r"peach_[a-f0-9]{32}",episode) is None:
            raise ValueError("Invalid episode identity")
        result = self.command("shell", "am", "start", "-S", "-W", "-n", PACKAGE+"/.MainActivity",
                              "--es", "episode_id", episode).decode()
        if "Status: ok" not in result:
            raise RuntimeError("App launch rejected")
        time.sleep(1)

    def capture(self, root, index, episode):
        self.phase = "observation"
        directory = Path(root)/"frames"/f"{index:03d}"
        directory.mkdir(parents=True, exist_ok=False)
        attempts = []
        # TCG guests under system contention can make the app window briefly
        # unreadable. Recapture is read-only and bounded; every attempt stays
        # recorded in the frame receipt for the strict verifier.
        waits = (2, 5, 10, 20)
        for attempt in range(1 + len(waits)):
            try:
                before = self.runtime()
                xml = self.ui()
                png = self.command("exec-out", "screencap", "-p")
                if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("PNG capture failed")
                database = self.command("exec-out", "run-as", PACKAGE, "cat", "databases/shopping.db")
                persisted = database_tables(database)
                after = self.runtime()
                if before != after or after != persisted:
                    raise RuntimeError("State changed while collecting evidence")
                session = after["eval_session"]
                if len(session)!=1 or session[0]["episode_id"]!=episode:
                    raise RuntimeError("App evidence belongs to a different episode")
                nodes = ui_nodes(xml,after["products"])
                if not nodes:
                    raise RuntimeError("Task app is not visible")
                artifacts = {}
                for name,value in {"runtime_before.json":json.dumps(before).encode(), "runtime.json":json.dumps(after).encode(),
                        "database.sqlite":database, "persisted_state.json":json.dumps(persisted).encode(),
                        "ui.xml":xml, "screen.png":png}.items():
                    (directory/name).write_bytes(value)
                    artifacts[name] = {"path":str((directory/name).relative_to(root)),"sha256":digest(value)}
                frame = {"index":index,"episode_id":episode,"time":stamp(),"stable":True,"errors":[],
                         "profile":PROFILE,"artifacts":artifacts,"ui":nodes,"tables":after,"capture_attempts":attempts}
                save(directory/"frame.json",frame)
                return frame
            except Exception as error:
                attempts.append({"attempt":attempt+1,"error":type(error).__name__+": "+str(error)})
                if attempt < len(waits):
                    time.sleep(waits[attempt])
        raise RuntimeError("No fresh, stable app evidence: "+json.dumps(attempts))

    def confirm_text(self, expected, stage):
        # Wait only for the requested text. Never replay input or submit a search.
        deadline = time.monotonic() + 60
        for _ in range(5):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            index = len(self.trace)
            try:
                tables = self.runtime(timeout=min(30, remaining))
                sessions = tables["eval_session"]
                if len(sessions) != 1 or not isinstance(sessions[0]["draft"], str):
                    raise ValueError("Search draft is not readable")
                session = sessions[0]
                confirmed = session["draft"] == expected
                self.input_readbacks.append({"stage": stage, "trace_index": index,
                    "expected": expected, "actual": session["draft"],
                    "episode_id": session["episode_id"], "confirmed": confirmed,
                    "raw": self.last_runtime_response})
                if confirmed:
                    return
            except Exception as error:
                entry = self.trace[index] if index < len(self.trace) else {}
                transient = (isinstance(error, RuntimeError) and str(error) == "Read-only SQLite provider unavailable"
                    and entry.get("returncode") == 0 and entry.get("bytes") == 0
                    and "java.lang.IllegalStateException: Read-only snapshot unavailable" in entry.get("stderr", ""))
                if not transient:
                    raise TextInputUnconfirmed(stage + ": state read failed: " + str(error)) from error
                self.input_readbacks.append({"stage": stage, "trace_index": index,
                    "expected": expected, "actual": None, "episode_id": None, "confirmed": False,
                    "error_code": "PROVIDER_SNAPSHOT_UNAVAILABLE", "raw": self.last_runtime_response})
            time.sleep(0.5)
        raise TextInputUnconfirmed(stage + ": requested text did not reach the app within bounded readbacks")

    def execute(self, action, target=None):
        self.input_readbacks = []
        if action["type"] != "type_text":
            return super().execute(action, target)
        left, top, right, bottom = target["bounds"]
        deadline = time.monotonic() + 120
        commands = [
            ["shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2)],
            ["shell", "input", "keycombination", "113", "29"],
            ["shell", "input", "keyevent", "KEYCODE_DEL"],
        ]
        commands += [["shell", "input", "text", shlex.quote(char.replace(" ", "%s"))]
                     for char in action["text"]]
        for command in commands:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Text dispatch deadline; input is never replayed")
            self.command(*command, timeout=min(30, remaining))
            if command[2] == "tap":
                # Focus-confirmed typing: never send characters before the field
                # itself reports focused. Probes are read-only and hash-recorded.
                self.focus_probes = []
                self.confirm_focus(action["element_id"], deadline)
        if action["type"] == "type_text":
            self.confirm_text(action["text"], "before_dismiss")
            # Dismiss only after the full draft is persisted; never submit search.
            self.command("shell", "input", "keyevent", "KEYCODE_BACK")
            self.confirm_text(action["text"], "after_dismiss")
