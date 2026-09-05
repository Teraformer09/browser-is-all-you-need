"""Offline fixtures only: no emulator, model API, or benchmark rollout is started."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zlib

from uber_clone_031.verification.registry import load_registry
from uber_clone_031.verification.runner import verify_episode
from uber_clone_031.verification.scoring import POLICY_IDS, score_episode, score_policy, training_rewards
from uber_clone_031.verification.checks import VERIFIERS
from uber_clone_031.integrations.prime_env import episode_reward
from test_verifier import xml_for


def votes(policy, values):
    return [{"verifier_id": f"{policy}.V{i}", "status": {-1:"FAIL", 0:"INVALID", 1:"PASS"}[value],
             "reward": value, "reason_code": "OFFLINE_TEST_FIXTURE", "failure_origin": "none",
             "evidence_refs": ["fixture.json"]} for i, value in enumerate(values, 1)]


def tiny_png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0\0\0\0")) + chunk(b"IEND", b"")


def fixture(root):
    registry = load_registry()
    package = registry["app"]["package"]
    state = {"contract_version": registry["app"]["contract_version"], "episode_id": "fixture-episode",
             "ride_action_sequence": "0", "journey_stage": "0", "ride_pickup": "", "ride_type": "",
             "ride_drop": "", "selected_ride": "", "payment": "", "screen": "ride",
             "ride_confirmed": "false", "ride_cancelled": "false", "sequence_error": "false"}
    frames, events = [], []
    actions = [(None, {}), ({"type":"type_text","element_id":"pickup_input","text":"Airport Road"}, {"ride_pickup":"Airport Road"}),
               ({"type":"tap_element","element_id":"ride_type_premium"}, {"ride_type":"Premium","journey_stage":"1"}),
               ({"type":"type_text","element_id":"drop_input","text":"City Centre"}, {"ride_drop":"City Centre"}),
               ({"type":"tap_element","element_id":"destination_search_button"}, {"journey_stage":"2"}),
               ({"type":"tap_element","element_id":"ride_option_premium"}, {"selected_ride":"Premium","journey_stage":"3"}),
               ({"type":"tap_element","element_id":"payment_card"}, {"payment":"card","journey_stage":"4"}),
               ({"type":"tap_element","element_id":"confirm_ride_button"}, {"journey_stage":"5","screen":"ride_booked","ride_confirmed":"true"})]
    def artifact(name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
    for index, (action, change) in enumerate(actions):
        before = copy.deepcopy(state)
        state.update(change, ride_action_sequence=str(index))
        events.append({"episode_id":"fixture-episode", "seq":index, "initial":index == 0,
                       "before":None if index == 0 else before, "state":copy.deepcopy(state),
                       "action":"fixture", "accepted":True, "reason":""})
        summary = "Pickup: {} | Ride: {} | Destination: {} | Cab: {} | Payment: {}".format(
            *(state[k] or "not set" for k in ("ride_pickup","ride_type","ride_drop","selected_ride","payment")))
        progress = "Booking step " + state["journey_stage"] + "/5 • Pickup: " + ("set" if state["ride_pickup"] else "not set")
        terminal = "Ride booked: Premium to City Centre" if index == 7 else "Ready to book"
        tree = ET.Element("hierarchy")
        nodes = []
        for target in registry["ui"]["semantic_targets"].values():
            ET.SubElement(tree, "node", {"resource-id":package+":id/"+target, "enabled":"true",
                                        "clickable":"true", "bounds":"[0,0][100,100]", "text":"", "class":"android.widget.Button"})
            nodes.append({"id":target, "resource_id":package+":id/"+target, "enabled":True, "clickable":True,
                          "bounds":[0,0,100,100], "class_name":"android.widget.Button"})
        for target, text in (("route_summary_text", summary), ("ride_progress_text", progress), ("final_status_text", terminal)):
            ET.SubElement(tree, "node", {"resource-id":package+":id/"+target, "enabled":"true", "text":text})
        xml = ET.tostring(tree, encoding="unicode")
        px = xml_for(state)
        frame = {"index":index, "time":"offline-fixture", "action":action, "is_action":index > 0,
                 "observation":{"prefs_xml":px, "ui_tree_xml":xml, "ui":nodes, "steps":index,
                                "observation_freshness":{"fresh":True}, "ui_error":None},
                 "runtime_probe":copy.deepcopy(state), "mutations":copy.deepcopy(events), "app_sequence":str(index),
                 "info":None if index == 0 else {"action_executed":True, "schema_valid":True,
                    "permission_granted":True, "target_interactable":True, "stage_transition_accepted":True,
                    "failure_origin":"none", "action_duration_ms":100, "execution_errors":[]},
                 "adb_events":[{"phase":"action", "args":["shell","input","tap","50","50"], "returncode":0}],
                 "state":artifact(f"states/{index:03d}.xml", px.encode()), "ui":artifact(f"ui/{index:03d}.xml", xml.encode()),
                 "screenshot":artifact(f"screenshots/{index:03d}.png", tiny_png())}
        frame["ocr"] = {"text":summary + " " + progress + " " + terminal,
                        "source_sha256":frame["screenshot"]["sha256"], "min_confidence":100, "engine":"OFFLINE_FIXTURE_NOT_OCR"}
        frames.append(frame)
    return {"registry":registry, "registry_valid":True, "frames":frames, "episode_id":"fixture-episode",
            "task_id":"uber_clone_031", "task_expected":registry["task"]["expected"], "max_steps":12,
            "run_dir":str(root), "capabilities":dict.fromkeys(registry["validity"]["required_capabilities"], True),
            "installed_apk":{"package":package, "sha256":"a"*64}, "expected_apk_sha256":"a"*64,
            "capability_receipts":[{"returncode":0}], "failure_origin":"none"}


class CoreScoringTests(unittest.TestCase):
    def test_all_243_vote_combinations(self):
        for values in itertools.product((-1, 0, 1), repeat=5):
            result = score_policy("T5", votes("T5", values))
            expected = 0 if all(v == 0 for v in values) else 1 if values.count(1) >= 2 else -1
            self.assertEqual(result["reward"], expected, values)
            self.assertEqual(result["policy_score"], (5 + values.count(1))/10)

    def test_exactly_two_passes_outvote_three_failures(self):
        result = score_policy("T5", votes("T5", (1, 1, -1, -1, -1)))
        self.assertEqual(result["reward"], 1)
        self.assertEqual(result["policy_score"], 0.7)
        self.assertTrue(result["conflicting_verdicts"])

    def test_one_pass_four_invalid_is_fail(self):
        self.assertEqual(score_policy("T5", votes("T5", (1, 0, 0, 0, 0)))["reward"], -1)

    def test_bad_result_shapes_are_pipeline_invalid(self):
        cases = [[], votes("T5", (1,)*5)[:4]]
        duplicate = votes("T5", (1,)*5); duplicate[-1]["verifier_id"] = "T5.V1"; cases.append(duplicate)
        bad = votes("T5", (1,)*5); bad[0]["reward"] = True; cases.append(bad)
        bad = votes("T5", (1,)*5); bad[0]["status"] = "INVALID"; cases.append(bad)
        for case in cases: self.assertEqual(score_policy("T5", case)["status"], "INVALID")

    def test_all_episode_aggregation_cases(self):
        base = [score_policy(pid, votes(pid, (1,)*5)) for pid in POLICY_IDS]
        self.assertEqual(score_episode(base)["reward"], 1)
        for replacement, expected in (((0,)*5, 0), ((-1,)*5, -1)):
            values = copy.deepcopy(base); values[0] = score_policy("V1", votes("V1", replacement))
            self.assertEqual(score_episode(values)["reward"], expected)
        values = copy.deepcopy(base); values[0] = score_policy("V1", votes("V1", (0,)*5))
        values[-1] = score_policy("T7", votes("T7", (-1,)*5))
        self.assertEqual(score_episode(values)["reward"], -1)
        self.assertEqual(score_episode(base[:-1])["status"], "INVALID")

    def test_explicit_training_filter(self):
        values = [{"status":s, "reward":r, "training_eligible":s != "INVALID"} for s,r in (("FAIL",-1),("INVALID",0),("PASS",1))]
        self.assertEqual(training_rewards(values), [-1, 1])
        with self.assertRaises(ValueError): training_rewards([{"reward":0}])

    def test_prime_signed_adapter_and_missing_verdict(self):
        for status, reward in (("PASS",1),("FAIL",-1),("INVALID",0)):
            self.assertEqual(episode_reward({"episode_verdict":{"status":status,"reward":reward}}), reward)
        state = {}
        self.assertEqual(episode_reward(state), 0)
        self.assertEqual(state["episode_verdict"]["reason_codes"], ["MISSING_EPISODE_VERDICT"])


class DedicatedVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.context = fixture(Path(self.tmp.name))
    def tearDown(self): self.tmp.cleanup()

    def test_exact_registry_and_all_seventy_happy_paths(self):
        result = verify_episode(self.context)
        self.assertEqual(len(VERIFIERS), 70)
        for policy in result["policies"]:
            for value in policy["verifier_results"]:
                with self.subTest(verifier=value["verifier_id"]):
                    self.assertEqual(value["status"], "PASS", value)
        self.assertEqual(result["reward"], 1)

    def test_each_of_70_has_explicit_missing_evidence_result(self):
        context = {**self.context, "frames":[]}
        result = verify_episode(context)
        self.assertEqual(result["status"], "INVALID")
        for p in result["policies"]:
            self.assertEqual(len(p["verifier_results"]), 5)
            self.assertTrue(all(r["status"] == "INVALID" and r["reason_code"] for r in p["verifier_results"]))

    def test_payment_state_cash_unset_stale_and_conflicts(self):
        for value in ("cash", ""):
            context = copy.deepcopy(self.context)
            frame = context["frames"][-1]
            state = dict(frame["runtime_probe"], payment=value)
            frame["runtime_probe"] = state
            frame["observation"]["prefs_xml"] = xml_for(state)
            for name in ("payment_from_preferences", "payment_from_runtime"):
                self.assertEqual(VERIFIERS[name][1](context)["status"], "FAIL")
        stale = copy.deepcopy(self.context)
        stale["frames"][-1]["runtime_probe"]["episode_id"] = "old"
        self.assertEqual(VERIFIERS["payment_from_runtime"][1](stale)["status"], "INVALID")
        conflict = copy.deepcopy(self.context)
        conflict["frames"][-1]["runtime_probe"]["payment"] = "cash"
        policy = next(p for p in verify_episode(conflict)["policies"] if p["policy_id"] == "T5")
        self.assertEqual(policy["status"], "PASS")
        self.assertTrue(policy["conflicting_verdicts"])

    def test_mutation_intentions_or_gaps_are_not_state_proof(self):
        for events in ([{"action":"click card"}], self.context["frames"][-1]["mutations"][:-1]):
            context = copy.deepcopy(self.context)
            context["frames"][-1]["mutations"] = events
            self.assertEqual(VERIFIERS["payment_from_mutations"][1](context)["status"], "INVALID")

    def test_low_confidence_ocr_is_invalid_not_a_false_failure(self):
        context = copy.deepcopy(self.context)
        context["frames"][-1]["ocr"].update(min_confidence=15, text="unreliable")
        self.assertEqual(VERIFIERS["payment_from_screenshot"][1](context)["status"], "INVALID")

    def test_unusable_specification_invalidates_all_slots(self):
        context = copy.deepcopy(self.context)
        context["task_expected"] = {}
        self.assertEqual(verify_episode(context)["status"], "INVALID")

    def test_card_button_only_is_not_payment_evidence(self):
        context = copy.deepcopy(self.context)
        frame = context["frames"][-1]
        frame["ocr"]["text"] = "Payment method Cash Card UPI"
        self.assertEqual(VERIFIERS["payment_from_screenshot"][1](context)["status"], "INVALID")

    def test_optional_image_missing_does_not_erase_assessable_success(self):
        context = copy.deepcopy(self.context)
        context["frames"][-1]["screenshot"] = None
        self.assertEqual(verify_episode(context)["reward"], 1)

    def test_generic_valid_cash_is_semantically_wrong(self):
        context = copy.deepcopy(self.context)
        frame = context["frames"][-2]
        frame["action"]["element_id"] = "payment_cash"
        self.assertEqual(VERIFIERS["mobile_action_schema"][1](context)["status"], "PASS")
        self.assertEqual(VERIFIERS["raw_tool_allowlist"][1](context)["status"], "PASS")
        for name in ("resource_semantic_map", "declared_operation_lookup", "post_state_semantic_effect",
                     "mutation_semantic_replay", "runtime_semantic_effect"):
            self.assertEqual(VERIFIERS[name][1](context)["status"], "FAIL")

    def test_pipeline_failure_is_not_an_agent_execution_failure(self):
        context = copy.deepcopy(self.context)
        context["frames"][-1]["info"].update(action_executed=False, failure_origin="pipeline", execution_errors=["offline"])
        self.assertEqual(VERIFIERS["receipt_execution"][1](context)["status"], "INVALID")

    def test_malformed_action_is_fail_not_invalid(self):
        context = copy.deepcopy(self.context)
        context["frames"][1]["action"] = []
        for name in ("mobile_action_schema","jsonschema_action_schema","manual_argument_contract",
                     "canonical_roundtrip","receipt_schema_reconciliation"):
            self.assertEqual(VERIFIERS[name][1](context)["status"], "FAIL")

    def test_wrong_target_is_fail_for_all_target_verifiers(self):
        context = copy.deepcopy(self.context)
        context["frames"][1]["action"]["element_id"] = "missing_button"
        for name in ("xml_target_interactability","observation_target_interactability","bounds_and_target_resolution",
                     "receipt_target_reconciliation","before_state_target_contract"):
            self.assertEqual(VERIFIERS[name][1](context)["status"], "FAIL")


if __name__ == "__main__": unittest.main()
