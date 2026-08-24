# Grade School validation evidence

This directory preserves exact Midband-RL-v2 Grade School candidates and the current-verifier audit used by `../VALIDATION_REPORT.md`.

Run the three validation stages from the repository root in the pinned environment:

```bash
python3 'Reward_GRPO/Grade_School Verifiers/validation/run_failure_gap_audit.py' --output-dir /tmp/grade-school-gap
python3 'Reward_GRPO/Grade_School Verifiers/validation/run_control_validation.py' --output-dir /tmp/grade-school-controls
python3 'Reward_GRPO/Grade_School Verifiers/validation/run_structure_validation.py' --output-dir /tmp/grade-school-structure
```

The gap and control runners require `STRANGE_ISOLATED_REPLAY=1`, GCC 13.3.0, immutable repository input, and a new empty output directory. The source evaluation used the fixed-26 overlay instructions, while the verifier package pins the pristine instructions; both hashes are preserved because their executable Grade School API and official test contract are the same.

| Artifact | Purpose |
|---|---|
| `failure_gap_manifest.json` | Pins source run, checkpoint, candidates, source evidence, and expected classifications |
| `cases/` | Exact model-produced `grade_school.h/.cpp` snapshots |
| `fixed/instructions.md` | Pristine contract authenticated by current verifiers |
| `fixed/source_overlay_instructions.md` | Exact prompt overlay used by the source evaluation |
| `failure_gap_replay_receipt.json` | Current-verifier classifications for all real candidates |
| `control_validation_receipt.json` | Positive, mutation, invalid, immutability, and repeatability evidence |
| `structure_validation_receipt.json` | Policy/verifier pairing and kernel inventory |
