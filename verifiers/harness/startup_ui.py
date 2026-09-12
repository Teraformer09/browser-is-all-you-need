"""Bounded first-boot System UI recovery before a task episode exists."""
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from amazon_cart_001.harness.evidence import digest, stamp


def _system_ui_target(xml, recovery):
    button_id, button_text = ("android:id/aerr_wait", "Wait") if recovery == "wait" else ("android:id/aerr_close", "Close app")
    nodes = [node.attrib for node in ET.fromstring(xml).iter("node")]
    if not nodes:
        raise ValueError("STARTUP_UI_EMPTY")
    titles = [n for n in nodes if n.get("resource-id") == "android:id/alertTitle"]
    errors = [n for n in titles if "isn't responding" in n.get("text", "").replace("’", "'")]
    if not errors:
        if any(n.get("resource-id") in {"android:id/aerr_wait", "android:id/aerr_close"} for n in nodes):
            raise RuntimeError("UNEXPECTED_STARTUP_APP_ERROR")
        return None
    if len(errors) != 1 or errors[0].get("package") != "android" or errors[0].get("text", "").replace("’", "'") != "System UI isn't responding":
        raise RuntimeError("UNEXPECTED_STARTUP_ANR")
    waits = [n for n in nodes if n.get("package") == "android"
             and n.get("resource-id") == button_id
             and n.get("text") == button_text and n.get("enabled") == "true"
             and n.get("clickable") == "true"]
    if len(waits) != 1:
        raise RuntimeError("AMBIGUOUS_SYSTEM_UI_WAIT")
    bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", waits[0].get("bounds", ""))
    if bounds is None:
        raise RuntimeError("INVALID_SYSTEM_UI_WAIT_BOUNDS")
    left, top, right, bottom = map(int, bounds.groups())
    if not (0 <= left < right <= 1080 and 0 <= top < bottom <= 2400):
        raise RuntimeError("INVALID_SYSTEM_UI_WAIT_BOUNDS")
    return (left + right) // 2, (top + bottom) // 2


def system_ui_wait_target(xml):
    return _system_ui_target(xml, "wait")


def system_ui_restart_target(xml):
    return _system_ui_target(xml, "restart")


def prepare_startup_ui(root, command, budget_seconds=120, initial_idle_seconds=0, recovery="wait"):
    if recovery not in ("wait", "restart"):
        raise ValueError("STARTUP_RECOVERY_INVALID")
    if type(initial_idle_seconds) not in (int, float) or not 0 <= initial_idle_seconds < budget_seconds:
        raise ValueError("STARTUP_IDLE_BUDGET_INVALID")
    directory = Path(root) / "startup"
    directory.mkdir(exist_ok=False)
    started = time.monotonic()
    deadline = started + budget_seconds
    quiet_since = None
    report = {"kind": "pre_episode_system_ui_readiness", "at": stamp(),
              "task_episode_started": False, "status": "STARTING",
              "system_wait_attempts": 0, "system_wait_taps": 0,
              "empty_dump_attempts": 0, "observations": [],
              "initial_idle_seconds": initial_idle_seconds, "idle_completed": False,
              "recovery_strategy": recovery, "system_restart_attempts": 0,
              "system_restart_commands_completed": 0, "process_restart_verified": False,
              "absent_restart_pid_attempts": 0, "failed_dump_attempts": 0}
    # External /sdcard storage may not be unlocked during first boot.
    remote = "/data/local/tmp/democart-startup-ui.xml"
    def call(args, timeout=15):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("SYSTEM_UI_STARTUP_TIMEOUT")
        return command(["adb", "-s", "emulator-5556", *args], timeout=min(timeout, remaining))
    def system_ui_pid(allow_absent=False):
        try:
            raw = call(["shell", "pidof", "com.android.systemui"], timeout=10).strip()
        except subprocess.CalledProcessError as exc:
            # pidof returns 1 with no output while the process is absent.
            # Only tolerate this after our completed system restart; transport
            # failures, timeouts and a missing pre-restart PID still fail.
            if allow_absent and exc.returncode == 1 and not (exc.stdout or "").strip() and not (exc.stderr or "").strip():
                return None
            raise
        if not re.fullmatch(r"[1-9][0-9]*", raw):
            raise RuntimeError("SYSTEM_UI_PID_UNAVAILABLE")
        return int(raw)
    try:
        # BOOT_COMPLETED starts asynchronous package/provider/System UI work.
        # Avoid launching UiAutomation into that first-boot burst. This is time
        # for the OS to settle, never evidence of readiness by itself.
        idle_until = started + initial_idle_seconds
        report["phase"] = "FIRST_BOOT_SETTLING"
        (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        while time.monotonic() < idle_until:
            remaining = min(idle_until, deadline) - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(15, remaining))
        report["idle_completed"] = True
        report["phase"] = "OBSERVING_UI"
        (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        while time.monotonic() < deadline:
            try:
                result = call(["shell", "uiautomator", "dump", remote], timeout=60)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as dump_error:
                # UiAutomation can be SIGKILLed (exit 137) or stall into a
                # timeout during first-boot TCG contention. Retry the read-only
                # observation within the shared deadline; never replay input.
                report["failed_dump_attempts"] += 1
                report["observations"].append({"dump_error": type(dump_error).__name__ + ": " + str(dump_error)[:200],
                                               "elapsed_seconds": round(time.monotonic() - started, 3)})
                (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
                # SIGKILL bursts cluster during first-boot contention; allow up to
                # five failed dumps while the shared deadline still has room.
                if report["failed_dump_attempts"] >= 5 or deadline - time.monotonic() < 20:
                    raise
                time.sleep(min(3, max(0, deadline - time.monotonic())))
                continue
            if not result.strip():
                # UIAutomator can return exit zero with no root during first boot.
                # Retry observation only, never a timed-out/unknown input action.
                report["empty_dump_attempts"] += 1
                if report["system_restart_commands_completed"]:
                    # System UI has just been closed. Its replacement may not
                    # expose a root immediately; use the remaining shared
                    # startup deadline for observations, never another tap.
                    report["phase"] = "WAITING_FOR_RESTARTED_UI"
                elif report["empty_dump_attempts"] >= 3:
                    raise RuntimeError("STARTUP_UI_DUMP_UNAVAILABLE")
                (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
                time.sleep(min(3, max(0, deadline - time.monotonic())))
                continue
            if "dumped to:" not in result:
                raise RuntimeError("STARTUP_UI_DUMP_FAILED")
            # Text-mode adb shell propagates cat failures; exec-out may return
            # exit zero with a Permission denied message instead of XML.
            xml = call(["shell", "cat", remote], timeout=5)
            raw = xml.encode()
            name = f"{len(report['observations']):03d}.xml"
            (directory / name).write_bytes(raw)
            observation = {"path": "startup/" + name, "sha256": digest(raw),
                           "elapsed_seconds": round(time.monotonic() - started, 3)}
            report["observations"].append(observation)
            target = _system_ui_target(xml, recovery)
            try:
                call(["shell", "rm", "-f", remote], timeout=5)
            except Exception as cleanup_error:
                observation["cleanup_error"] = type(cleanup_error).__name__ + ": " + str(cleanup_error)
            now = time.monotonic()
            if target is not None:
                if recovery == "restart":
                    if report["system_restart_attempts"] >= 1:
                        raise RuntimeError("REPEATED_SYSTEM_UI_ANR")
                    report["system_ui_pid_before"] = system_ui_pid()
                    counter, completed = "system_restart_attempts", "system_restart_commands_completed"
                else:
                    if report["system_wait_attempts"] >= 2:
                        raise RuntimeError("REPEATED_SYSTEM_UI_ANR")
                    counter, completed = "system_wait_attempts", "system_wait_taps"
                # Only the positively identified Android system dialog, before
                # creating/resetting the task. Never an actor-step substitution.
                action_receipt = {"kind": "system_ui_" + recovery, "x": target[0], "y": target[1],
                                  "status": "DISPATCHED"}
                observation["recovery"] = action_receipt
                report[counter] += 1
                (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
                try:
                    call(["shell", "input", "tap", str(target[0]), str(target[1])], timeout=30)
                except Exception as exc:
                    action_receipt.update(status="OUTCOME_UNKNOWN", error=type(exc).__name__ + ": " + str(exc))
                    raise
                report[completed] += 1
                action_receipt["status"] = "COMMAND_COMPLETED"
                quiet_since = None
            else:
                if recovery == "restart" and report["system_restart_attempts"]:
                    current_pid = system_ui_pid(allow_absent=True)
                    observation["system_ui_pid"] = current_pid
                    if current_pid is None:
                        report["absent_restart_pid_attempts"] += 1
                        report["process_restart_verified"] = False
                        report["phase"] = "WAITING_FOR_RESTARTED_PROCESS"
                        quiet_since = None
                        (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
                        time.sleep(min(3, max(0, deadline - time.monotonic())))
                        continue
                    report["system_ui_pid_after"] = current_pid
                    report["process_restart_verified"] = current_pid != report["system_ui_pid_before"]
                    if not report["process_restart_verified"]:
                        raise RuntimeError("SYSTEM_UI_RESTART_NOT_CONFIRMED")
                quiet_since = now if quiet_since is None else quiet_since
                if now - started >= 60 and now - quiet_since >= 15:
                    report["status"] = "READY"
                    report["phase"] = "READY"
                    return report
            time.sleep(min(3, max(0, deadline - time.monotonic())))
        raise TimeoutError("SYSTEM_UI_STARTUP_TIMEOUT")
    except Exception as exc:
        report.update(status="FAILED", error=type(exc).__name__ + ": " + str(exc))
        raise
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        (directory / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
