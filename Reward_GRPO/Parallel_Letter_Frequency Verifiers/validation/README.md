# Parallel Letter Frequency validation evidence

This directory preserves the real-output-first Strange audit run on 2026-08-23.

| Artifact | Purpose |
|---|---|
| `failure_gap_manifest.json` | Pins the Midband source run, source receipts, exact candidates, contract, and current verifier bytes |
| `cases/` | Six replayable candidate snapshots: two official passes and both turns from each failed trial |
| `fixed/instructions.md` | Authenticated Midband task overlay installed over the local pristine fixture |
| `failure_gap_replay_receipt.json` | All current policies replayed against every saved candidate |
| `control_validation_receipt.json` | Positive, focused defect, evaluator-fault, source-immutability, and repeatability results |
| `structure_validation_receipt.json` | Policy/verifier pairing, AST, ID, comment, and kernel-count evidence |

Run the three validators only in the pinned offline image with the repository mounted read-only, an empty writable output directory, `PYTHONDONTWRITEBYTECODE=1`, and `STRANGE_ISOLATED_REPLAY=1` for the gap/control runners. The commands exercised on 2026-08-23 are encoded by `run_failure_gap_audit.py`, `run_control_validation.py`, and `run_structure_validation.py`.

The local fixture is `local-results/job22-iter5-fixed26-v5-pathfix-20260814T071410Z/benchmark-output-shard-1/cpp/exercises/practice/parallel-letter-frequency`. The validators replace only its pristine instructions and candidate source files inside a temporary copy; the repository and saved candidates remain unchanged.
