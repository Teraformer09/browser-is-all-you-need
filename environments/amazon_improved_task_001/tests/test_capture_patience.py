"""Patient read-only recapture under TCG contention; never an input replay.

Synthetic fakes only: no Android, model, Prime API or billed evaluation.
"""
import copy
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree.ElementTree import Element, SubElement, tostring

from amazon_improved_task_001.harness.peach import PACKAGE, PeachDevice
from amazon_improved_task_001.harness.startup_ui import prepare_startup_ui
from test_startup_ui import CLEAN
from test_strict_verification import png

EPISODE = "peach_" + "a" * 32
TABLES = dict(
    products=[dict(id=1, sku="DC001", name="Nimbus Wireless Headphones",
                   category="Electronics", price_paise=249900)],
    cart=[], search_history=[],
    eval_events=[dict(sequence=0, kind="reset", payload=json.dumps({"episode_id": EPISODE}))],
    eval_session=[dict(singleton=1, episode_id=EPISODE, page="home", draft="", query="")])


def visible_xml():
    root = Element("hierarchy")
    SubElement(root, "node", {"package": PACKAGE, "resource-id": PACKAGE + ":id/etSearchBox",
        "content-desc": "", "text": "", "enabled": "true", "clickable": "true",
        "class": "android.widget.EditText", "bounds": "[10,10][900,60]"})
    return tostring(root)


def database_bytes(tables):
    with sqlite3.connect(":memory:") as db:
        for name, rows in tables.items():
            columns = list(rows[0]) if rows else {"cart": ["product_id", "qty"],
                                                  "search_history": ["query", "searched_at"]}[name]
            db.execute("CREATE TABLE " + name + "(" + ",".join(columns) + ")")
            for row in rows:
                db.execute("INSERT INTO " + name + " VALUES (" + ",".join("?" for _ in columns) + ")",
                           list(row.values()))
        db.commit()
        return db.serialize()


class FlakyVisibilityDevice(PeachDevice):
    """First `invisible` UI reads expose no app window; later reads are healthy."""

    def __init__(self, invisible):
        super().__init__("FAKE")
        self.invisible, self.reads = invisible, 0

    def runtime(self, timeout=30):
        self.trace.append({"args": ["runtime"], "phase": self.phase, "returncode": 0})
        return copy.deepcopy(TABLES)

    def ui(self):
        self.reads += 1
        raw = tostring(Element("hierarchy")) if self.reads <= self.invisible else visible_xml()
        self.trace.append({"args": ["ui"], "phase": self.phase, "returncode": 0,
                           "bytes": len(raw)})
        return raw

    def command(self, *args, timeout=30):
        raw = b""
        if args[:3] == ("exec-out", "screencap", "-p"):
            raw = png()
        elif args[:2] == ("exec-out", "run-as"):
            raw = database_bytes(TABLES)
        self.trace.append({"args": list(args), "phase": self.phase, "returncode": 0,
                           "bytes": len(raw)})
        return raw


class CapturePatienceTests(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        sleeper = patch("time.sleep", side_effect=self.sleeps.append)
        sleeper.start()
        self.addCleanup(sleeper.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def capture(self, device):
        return device.capture(Path(self.temp.name), 0, EPISODE)

    def test_transient_invisibility_recaptures_without_replay(self):
        device = FlakyVisibilityDevice(2)
        frame = self.capture(device)
        self.assertEqual(self.sleeps, [2, 5])
        self.assertEqual(len(frame["capture_attempts"]), 2)
        self.assertTrue(frame["stable"])
        self.assertFalse(any(t["args"][:2] == ["shell", "input"] for t in device.trace))

    def test_persistent_invisibility_fails_closed_after_bounded_waits(self):
        with self.assertRaisesRegex(RuntimeError, "No fresh, stable app evidence"):
            self.capture(FlakyVisibilityDevice(99))
        self.assertEqual(self.sleeps, [2, 5, 10, 20])


class StartupDumpTimeoutTests(unittest.TestCase):
    def test_startup_dump_allows_sixty_seconds_within_shared_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            clock = [0.0]
            calls = []
            def command(args, **kwargs):
                calls.append((args, kwargs))
                clock[0] += 1
                if "dump" in args:
                    return "UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml"
                if "cat" in args:
                    return CLEAN
                return ""
            with patch("time.monotonic", side_effect=lambda: clock[0]), \
                 patch("time.sleep", side_effect=lambda s: clock.__setitem__(0, clock[0] + s)):
                report = prepare_startup_ui(Path(temp), command)
            self.assertEqual(report["status"], "READY")
            dumps = [kwargs for args, kwargs in calls if "dump" in args]
            self.assertTrue(dumps and all(k["timeout"] == 60 for k in dumps))


class FocusSettleTests(unittest.TestCase):
    def test_focus_confirmed_by_probe_before_clear_and_chars(self):
        from test_text_readback import ReadbackDevice, TARGET, TEXT
        sleeps = []
        with patch("time.sleep", side_effect=sleeps.append):
            device = ReadbackDevice([TEXT, TEXT])
            device.execute({"type": "type_text", "element_id": "search_input", "text": TEXT}, TARGET)
        self.assertEqual(sleeps[0], 2)  # settle after the focus probe confirms
        commands = device.commands
        tap = commands.index(["shell", "input", "tap", "55", "35"])
        self.assertEqual(commands[tap + 1], ["shell", "input", "keycombination", "113", "29"])
        self.assertTrue(device.focus_probes and device.focus_probes[-1]["focused"] is True)

    def test_command_sequence_matches_audited_contract(self):
        from test_text_readback import ReadbackDevice, TARGET, TEXT
        from amazon_improved_task_001.verification.strict import expected_inputs
        with patch("time.sleep"):
            device = ReadbackDevice([TEXT, TEXT])
            device.execute({"type": "type_text", "element_id": "search_input", "text": TEXT}, TARGET)
        node = {"bounds": [10, 10, 100, 60]}
        expected = expected_inputs({"type": "type_text", "element_id": "search_input", "text": TEXT},
                                   node, transport="persisted_text_chars_v1")
        actual = [c for c in device.commands if c[:2] == ["shell", "input"]]
        self.assertEqual(actual, expected)


class ActionDumpTimeoutTests(unittest.TestCase):
    def test_action_phase_dump_allows_sixty_seconds(self):
        from test_ui_read_retry import EmptyRootDevice
        device = EmptyRootDevice(0)
        seen = []
        original = device.command
        def observing(*args, **kwargs):
            seen.append((args, kwargs))
            return original(*args, **kwargs)
        device.command = observing
        device.ui()
        dumps = [k for a, k in seen if a[:3] == ("shell", "uiautomator", "dump")]
        self.assertTrue(dumps and all(k.get("timeout") == 60 for k in dumps))


class ServeBudgetTests(unittest.TestCase):
    def test_software_serve_budget_covers_boot_gate_and_episode(self):
        from amazon_improved_task_001.harness.emulator_config import runtime_options
        options = runtime_options("software")
        budget = (options["boot_timeout_seconds"] + options["package_ready_timeout_seconds"] +
                  options["install_timeout_seconds"] + options["startup_ui_timeout_seconds"] +
                  options["episode_timeout_seconds"] + 30)
        self.assertEqual(budget, 2850)
        source = (Path(__file__).resolve().parents[1] /
                  "amazon_improved_task_001/harness/hosted_worker.py").read_text()
        self.assertIn('"startup_ui_timeout_seconds"]', source.split("def serve")[1].split("deadline")[0])


class StartupDumpRetryTests(unittest.TestCase):
    def run_gate(self, dump_failures):
        with tempfile.TemporaryDirectory() as temp:
            clock = [0.0]
            calls = []
            def command(args, **kwargs):
                calls.append((args, kwargs))
                clock[0] += 1
                if "dump" in args:
                    if len([1 for a, _ in calls if "dump" in a]) <= dump_failures:
                        raise subprocess.CalledProcessError(137, args)
                    return "UI hierarchy dumped to: /data/local/tmp/democart-startup-ui.xml"
                if "cat" in args:
                    return CLEAN
                return ""
            with patch("time.monotonic", side_effect=lambda: clock[0]), \
                 patch("time.sleep", side_effect=lambda s: clock.__setitem__(0, clock[0] + s)):
                try:
                    report = prepare_startup_ui(Path(temp), command)
                    return report, calls, None
                except Exception as exc:
                    report = json.loads((Path(temp) / "startup/manifest.json").read_text())
                    return report, calls, exc

    def test_transient_sigkill_dump_retries_then_ready(self):
        report, calls, error = self.run_gate(2)
        self.assertIsNone(error)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["failed_dump_attempts"], 2)
        self.assertEqual(len([o for o in report["observations"] if "dump_error" in o]), 2)
        self.assertTrue(any("sha256" in o for o in report["observations"]))
        self.assertFalse(any("input" in a for a, _ in calls))

    def test_five_failed_dumps_fail_closed(self):
        report, calls, error = self.run_gate(5)
        self.assertIsNotNone(error)
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["failed_dump_attempts"], 5)
        self.assertEqual(report["system_wait_taps"], 0)

    def test_four_failed_dumps_still_recover(self):
        report, calls, error = self.run_gate(4)
        self.assertIsNone(error)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["failed_dump_attempts"], 4)


class SandboxPatienceTests(unittest.TestCase):
    def test_creation_wait_uses_sixty_attempt_budget(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from amazon_improved_task_001.integrations.hosted_session import HostedSession
        with tempfile.TemporaryDirectory() as temp:
            session = HostedSession(temp)
            session.client = MagicMock()
            session.client.create.return_value = SimpleNamespace(id="sandbox-test")
            session.client.start_background_job.return_value = SimpleNamespace(job_id="job-test")
            with patch.object(session, "call", return_value={}):
                session.start()
            kwargs = session.client.wait_for_creation.call_args
            self.assertEqual(kwargs.kwargs["max_attempts"], 60)


if __name__ == "__main__":
    unittest.main()
