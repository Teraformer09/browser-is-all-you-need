from __future__ import annotations
import hashlib
import json
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from uuid import uuid4
from uber_clone_031.harness.backend.adb_device import AdbDevice, UiNode
from uber_clone_031.harness.backend.apk_env import ApkAction, DummyApkEnv
from uber_clone_031.harness.backend.core.actions import ActionValidationError, MobileAction
from uber_clone_031.harness.backend.env import StepResult
from uber_clone_031.verification.records import parse_state, verify

class RideStageEnv(DummyApkEnv):
    """Same reset/ADB actions as upstream; acceptance and termination are explicit."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.execution_errors = []

    def reset(self):
        self.execution_errors = []
        return super().reset()

    def observe(self):
        self.device.phase = "observation"
        ui_xml, prefs, ui_error = "", "", None
        try:
            ui_xml = self.device.dump_ui()
            self.ui_tree_xml = ui_xml
        except Exception as exc:
            ui_error = f"UI capture: {type(exc).__name__}: {exc}"
            self.execution_errors.append(ui_error)
            self.ui_tree_xml = None
        try:
            prefs = self.device.read_shared_prefs()
        except Exception as exc:
            self.execution_errors.append(f"State capture: {type(exc).__name__}: {exc}")
        nodes = self.device._resource_nodes_from_xml(ui_xml, self.task.resource_names) if ui_xml else []
        if ui_xml:
            attributes = {e.get("resource-id"): e.attrib for e in ET.fromstring(ui_xml).iter("node")}
            for node in nodes:
                node["enabled"] = attributes.get(node.get("resource_id"), {}).get("enabled") == "true"
        score = verify(self.task, prefs, steps=self.steps, invalid=self.invalid_action_seen,
                       forbidden=self.forbidden_action_seen, execution_errors=self.execution_errors)
        return {"task_id": self.task.task_id, "episode_id": self.task.episode_id,
                "goal": self.task.goal, "steps": self.steps, "max_steps": self.max_steps,
                "done": self.done, "ui": nodes, "ui_tree_xml": ui_xml, "ui_error": ui_error,
                "observation_freshness": getattr(self.device, "observation_freshness", {}),
                "last_action": self.last_action, "last_error": self.last_error,
                "apk_state": score["actual_state"], "prefs_xml": prefs, "scorecard": score,
                "reward": score["reward"], "final_reward": score["final_reward"],
                "exact_success": score["safe_success"]}

    def _coerce_action(self, raw_action):
        if isinstance(raw_action, ApkAction):
            raw_action = raw_action.to_mobile_dict()
        try:
            return ApkAction.from_mobile_action(MobileAction.parse_json(raw_action))
        except (TypeError, ValueError, AttributeError) as exc:
            if isinstance(exc, ActionValidationError):
                raise
            raise ActionValidationError("invalid_action_schema") from exc

    def _eligibility_error(self, action, obs):
        state = obs.get("apk_state", {})
        try:
            stage = int(state.get("journey_stage", "-1"))
        except ValueError:
            stage = -1
        target = action.target or ""
        if action.action == "finish":
            return None if obs["scorecard"]["safe_success"] else "Booking is incomplete; finish rejected. Continue the task."
        if action.action in {"press_home", "tap_coordinates"}:
            return "This action is not permitted; use the declared resource-ID tools."
        if action.action in {"click_resource", "input_resource"}:
            if target not in self.task.resource_names:
                return f"Unknown UI target: {target}"
            if target.startswith("payment_") and stage < 3:
                return "Choose a cab before selecting payment."
            if target.startswith("ride_option_") and stage < 2:
                return "Search the destination before choosing a cab."
            if target == "destination_search_button" and stage < 1:
                return "Choose a ride type before searching the destination."
            if target == "confirm_ride_button" and (stage != 4 or not state.get("ride_pickup")):
                return "Set pickup, ride type, destination, cab and payment before booking."
            visible = next((node for node in obs["ui"] if node.get("id") == target), None)
            if not visible or not visible.get("enabled"):
                return f"Target not visible/enabled: {target}; use an explicit swipe if needed."
            if action.action == "input_resource" and target not in {"pickup_input", "drop_input"}:
                return "Text entry is allowed only in pickup_input or drop_input."
        return None

    def step(self, raw_action):
        if self.done:
            obs = self.observe()
            return StepResult(obs, obs["reward"], True, {"error": "environment already done", "action_executed": False})
        before = self.observe()
        self.steps += 1
        self.last_error = None
        self.last_action = raw_action if isinstance(raw_action, dict) else {"raw": str(raw_action)}
        executed, accepted, schema_valid = False, None, True
        permission, target_interactable, origin = False, None, "none"
        action_started = time.monotonic()
        try:
            action = self._normalize_action(self._coerce_action(raw_action))
            self.last_action = action.to_dict()
            permission = action.action in {"click_resource", "input_resource", "press_back", "swipe", "wait", "finish"}
            if action.action in {"click_resource", "input_resource"}:
                node = next((n for n in before["ui"] if n.get("id") == action.target), None)
                target_interactable = bool(node and node.get("enabled") and
                                           (node.get("clickable") or str(node.get("class_name", "")).endswith("EditText")))
            self.last_error = self._eligibility_error(action, before)
            if action.action in {"press_home", "tap_coordinates"}:
                self.forbidden_action_seen = True
            if self.last_error:
                accepted, origin = False, "agent"
            else:
                self.device.phase = "action"
                self._execute(action)
                executed = True
        except ActionValidationError as exc:
            self.last_error, schema_valid, accepted, origin = exc.reason, False, False, "agent"
        except LookupError as exc:
            self.last_error, accepted, origin = str(exc), False, "pipeline"
            self.execution_errors.append("Target execution: " + str(exc))
        except Exception as exc:
            origin = "pipeline"
            self.last_error = f"Execution error: {type(exc).__name__}: {exc}"
            self.execution_errors.append(self.last_error)
        action_duration_ms = round((time.monotonic() - action_started) * 1000, 2)
        obs = self.observe()
        old_seq = before.get("apk_state", {}).get("ride_action_sequence")
        state = obs["apk_state"]
        if executed and state.get("ride_action_sequence") != old_seq:
            accepted = state.get("last_action_accepted") == "true"
            if not accepted:
                self.last_error = state.get("last_action_error") or "App rejected the action."
                origin = "agent"
        if self.last_error:
            self.invalid_action_seen = True
        obs["last_error"] = self.last_error
        success = obs["scorecard"]["safe_success"]
        self.done = success or self.steps >= self.max_steps or self.reset_failed
        obs["done"] = self.done
        info = {"action_valid": schema_valid and executed, "schema_valid": schema_valid,
                "action_executed": executed, "stage_transition_accepted": accepted,
                "permission_granted": permission, "target_interactable": target_interactable,
                "failure_origin": origin, "action_duration_ms": action_duration_ms,
                "rejection_reason": self.last_error, "error": self.last_error,
                "termination_reason": "task_success" if success else "step_budget" if self.done else None,
                "completed_stages": obs["scorecard"]["completed_stages"], "total_stages": 6,
                "execution_errors": list(self.execution_errors)}
        return StepResult(obs, obs["reward"], self.done, info)
