# Complex Numbers validation evidence

All model-output replays and controls run offline in the pinned validation image with GCC 13.3.0. The exact Midband-RL-v2 sources and instruction contract are stored below this directory; protected task assets are copied from the authenticated local fixture only at replay time.

| Artifact | Purpose | Result |
|---|---|---|
| `failure_gap_manifest.json` | Source identities, outcomes, baseline restriction, and current verifier identities | 8 authenticated samples |
| `run_failure_gap_audit.py` | Exact post-fix replay against E01–E05 | 7 agreement-fails, 1 agreement-pass, 0 misses/restrictions |
| `failure_gap_replay_receipt.json` | Machine-readable replay evidence | PASS |
| `e04_stream_format_restriction_baseline_receipt.json` | Exact official-positive false-negative from baseline E04 | E04-A FAIL solely on unsupported text format |
| `run_control_validation.py` | Positive, defect, invalid-evaluator, immutability, and repeatability controls | 3 positives, 8 defects, 2 invalid, 5 repeatable policies |
| `control_validation_receipt.json` | Machine-readable control evidence | PASS |
| `run_structure_validation.py` | Policy/verifier pairing, IDs, AST, comments, and kernel inventory | 5 pairs, 15 kernels |
| `structure_validation_receipt.json` | Machine-readable structure evidence | PASS |

The human-readable decision record is `../VALIDATION_REPORT.md`. The verifier package is ready for the pinned task; GRPO integration remains conditional on terminal E03 enforcement and `INVALID` sample exclusion.
