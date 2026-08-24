# Clock validation artifacts

This directory binds six exact Midband-RL-v2 candidates to the unchanged Clock verifier package. `failure_gap_manifest.json` pins evaluation provenance, candidate bytes, and expected classifications; `fixed/instructions.md` preserves the exact protected instruction asset used by that evaluation.

Run the scripts in the pinned offline validation image with the repository read-only, a new empty `/output`, `--network none`, and `STRANGE_ISOLATED_REPLAY=1` for failure-gap and control runs. The saved top-level receipts are normalized evidence; compiler logs and per-kernel binaries remain ephemeral.

| Script | Step | Saved receipt |
|---|---|---|
| `run_failure_gap_audit.py` | Exact model-output replay against unchanged E01–E05 | `failure_gap_replay_receipt.json` |
| `run_structure_validation.py` | Policy/verifier pairing, AST, IDs, kernel inventory | `structure_validation_receipt.json` |
| `run_control_validation.py` | Positives, real failures, mutant, invalid faults, repeatability | `control_validation_receipt.json` |
