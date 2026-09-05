# Policy rubrics and dedicated verifier entry points

The task checks one simulated Premium/CARD booking. Each row below is one complete
policy claim; its five verifiers use their own applicable evidence and return an
explicit PASS, FAIL or INVALID result. State observations are not agent claims.

This is an implemented deterministic registry, not a learned universal verifier
or an empirically calibrated voting system. The exact user-requested rule is
0.5 + 0.1 × PASS count, with >=0.7 passing, all-invalid returning 0, and every other
nonpassing policy returning -1. Episode reward is FAIL-first, then INVALID, then PASS.

| Policy | Complete claim | Five registered verifier entry points | Failure / invalid boundary |
|---|---|---|---|
| V1 | Specification and capability readiness | `V1.V1: schema_and_capabilities`<br>`V1.V2: yaml_and_capability_receipts`<br>`V1.V3: registry_and_live_contract`<br>`V1.V4: installed_app_and_tools`<br>`V1.V5: runtime_schema_and_capabilities` | Missing configuration, mismatched APK/contract or absent required capability → INVALID. |
| V2 | Episode and evidence integrity | `V2.V1: preference_episode_chain`<br>`V2.V2: artifact_hash_chain`<br>`V2.V3: mutation_episode_chain`<br>`V2.V4: runtime_snapshot_chain`<br>`V2.V5: capture_and_receipt_alignment` | Unreliable episode identity, broken frame chain or unusable evidence → INVALID; no unsupported agent-tampering inference. |
| G1 | Action-format compliance | `G1.V1: mobile_action_schema`<br>`G1.V2: jsonschema_action_schema`<br>`G1.V3: manual_argument_contract`<br>`G1.V4: canonical_roundtrip`<br>`G1.V5: receipt_schema_reconciliation` | Malformed actor JSON/arguments → FAIL; unavailable action records → INVALID. |
| G2 | Tool-permission compliance | `G2.V1: raw_tool_allowlist`<br>`G2.V2: canonical_tool_allowlist`<br>`G2.V3: declarative_permission_rules`<br>`G2.V4: receipt_permission_audit`<br>`G2.V5: forbidden_trace_reconciliation` | Unsupported/prohibited actor tool → FAIL; unavailable permissions/receipts → INVALID. |
| G3 | UI-target availability | `G3.V1: xml_target_interactability`<br>`G3.V2: observation_target_interactability`<br>`G3.V3: bounds_and_target_resolution`<br>`G3.V4: receipt_target_reconciliation`<br>`G3.V5: before_state_target_contract` | Known missing/disabled/noninteractable target → FAIL; unavailable contemporaneous UI → INVALID. |
| G4 | Tool-execution correctness | `G4.V1: receipt_execution`<br>`G4.V2: adb_command_completion`<br>`G4.V3: post_action_receipt_alignment`<br>`G4.V4: execution_error_audit`<br>`G4.V5: transport_and_effect_reconciliation` | Agent-originated tool rejection → FAIL; transport/harness uncertainty → INVALID. App acceptance is separate. |
| S1 | Semantic-target correctness | `S1.V1: resource_semantic_map`<br>`S1.V2: declared_operation_lookup`<br>`S1.V3: post_state_semantic_effect`<br>`S1.V4: mutation_semantic_replay`<br>`S1.V5: runtime_semantic_effect` | Wrong task-bound semantic choice → FAIL; unresolved semantic/state evidence → INVALID. |
| T1 | Pickup correctness | `T1.V1: pickup_from_preferences`<br>`T1.V2: pickup_from_accessibility`<br>`T1.V3: pickup_from_screenshot`<br>`T1.V4: pickup_from_mutations`<br>`T1.V5: pickup_from_runtime` | Final pickup must be Airport Road. Observed wrong/unset → FAIL; unreadable → INVALID. |
| T2 | Ride-type correctness | `T2.V1: ride_type_from_preferences`<br>`T2.V2: ride_type_from_accessibility`<br>`T2.V3: ride_type_from_screenshot`<br>`T2.V4: ride_type_from_mutations`<br>`T2.V5: ride_type_from_runtime` | Final ride type must be Premium. Observed wrong/unset → FAIL; unreadable → INVALID. |
| T3 | Destination correctness | `T3.V1: destination_from_preferences`<br>`T3.V2: destination_from_accessibility`<br>`T3.V3: destination_from_screenshot`<br>`T3.V4: destination_from_mutations`<br>`T3.V5: destination_from_runtime` | Final destination must be City Centre. Observed wrong/unset → FAIL; unreadable → INVALID. |
| T4 | Cab correctness | `T4.V1: cab_from_preferences`<br>`T4.V2: cab_from_accessibility`<br>`T4.V3: cab_from_screenshot`<br>`T4.V4: cab_from_mutations`<br>`T4.V5: cab_from_runtime` | Final cab must be Premium. Observed wrong/unset → FAIL; unreadable → INVALID. |
| T5 | Payment-method correctness | `T5.V1: payment_from_preferences`<br>`T5.V2: payment_from_accessibility`<br>`T5.V3: payment_from_screenshot`<br>`T5.V4: payment_from_mutations`<br>`T5.V5: payment_from_runtime` | Effective payment must be card. A visible CARD button is insufficient. Wrong/unset → FAIL; unreadable → INVALID. |
| T6 | Booking completion | `T6.V1: booking_from_preferences`<br>`T6.V2: booking_from_accessibility`<br>`T6.V3: booking_from_screenshot`<br>`T6.V4: booking_from_mutations`<br>`T6.V5: booking_from_runtime` | Confirmed, not cancelled, stage 5, ride_booked. Incomplete/wrong terminal facts → FAIL; unavailable facts → INVALID. |
| T7 | Required action-contract compliance | `T7.V1: contract_from_receipts`<br>`T7.V2: contract_from_action_replay`<br>`T7.V3: contract_from_mutations`<br>`T7.V4: contract_from_runtime_history`<br>`T7.V5: contract_from_transport_audit` | No invalid/prohibited actions, clean sequence, within budget. Proven violation → FAIL; unavailable audit evidence → INVALID. |

For T1–T6, the five evidence strategies are persisted preferences, accessibility
summary, screenshot OCR summary, complete actual mutation replay, and a protected
read-only runtime probe. Every strategy checks the row's full predicate. The
runtime payment alias is not counted as an extra strategy. Generic verifiers
share low-level schema/evidence readers and some complete-claim gates; their
correlation is explicit, not disguised as independent statistical confidence.

Each result stores verifier_id, status, reward, reason_code, failure_origin,
observed_value, expected_value and evidence_refs. Each policy stores all five
results, PASS/FAIL/INVALID counts, support score, status and disagreements.
Missing or duplicate IDs never disappear from the denominator. The registry
and implementation hashes are recorded with each run.

Direct verification performed here uses offline fixtures, exhaustive scoring
combinations, source installation and builds. Live end-to-end validation of this
new 70-verifier path is intentionally pending user approval; these tests are not
second-evaluation results.

## v0.6.0 checkpoint reporting

The fourteen policy definitions, five-verifier threshold and terminal -1/0/1
aggregation are unchanged. The runner additionally evaluates those same
predicates on each recorded prefix. These are **provisional checkpoint results**,
not terminal training rewards. A later edit can revoke an earlier policy PASS.

Unfinished task policies display PENDING rather than treating not-yet-completed
work as terminal failure. Their raw five votes remain in `checkpoints/<frame>.json`.
No extra PASS vote is manufactured, and no checkpoint result replaces the final
episode assessment. Missing evidence for a due check remains INVALID.

`progress_history.json` and `progress_report.md` show per-step policy rewards,
newly completed stages and the separate PENDING/final episode reward. Prime
receives these files, the ordered reward timeline, and individual policy/stage
metrics. Repeating a passed action adds no reward. An eventual G4 or T7 failure
still makes the final episode FAIL under the unchanged aggregation rule.
