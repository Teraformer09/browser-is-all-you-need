# Circular Buffer validation artifacts

This directory binds exact Midband-RL-v2 source snapshots to the current verifier package. `failure_gap_manifest.json` pins provenance and expected classifications; `baseline_contract.py` preserves the pre-audit one-file boundary; `fixed/instructions.md` preserves the exact source-evaluation instruction asset.

Run each script in the pinned offline validation image with the repository mounted read-only, a new empty output directory mounted at `/output`, `--network none`, and `STRANGE_ISOLATED_REPLAY=1` for the failure-gap and control campaigns. The saved top-level receipts are the normalized evidence used by `../VALIDATION_REPORT.md`; per-kernel build products and logs are intentionally ephemeral.

| Script | Step | Saved receipt |
|---|---|---|
| `run_failure_gap_audit.py` | Exact model-output replay, baseline/current comparison | `failure_gap_replay_receipt.json` |
| `run_structure_validation.py` | Policy/verifier pairing, AST, IDs, inventory | `structure_validation_receipt.json` |
| `run_control_validation.py` | Positives, real defects, mutant, invalid faults, repeatability | `control_validation_receipt.json` |
