# Circular Buffer Verifier Validation Report

| Report field | Value |
|---|---|
| Topic | Circular Buffer |
| Source evaluation | `execution-bank-RL-v2-think-r2/fixed26-mt2-4x-20260818` |
| Source checkpoint | `execution-bank-RL-v2-think-r2/checkpoints/grpo_lora_r16/iter_0000019/adapter` |
| Source outcomes | pass@1 `1/4`; pass by turn 2 `2/4` |
| Validation image | `glm47-reward-grpo-bank-account@sha256:e4d1090d07cab73e5c4137637beccebe1dac0f6aa440e7d4cbfc466c4f226932` |
| Compiler | GCC `13.3.0` |
| Policies and kernels | 5 policy/verifier pairs; 15 candidate kernels |
| Verifier-package readiness | `READY` for the pinned canonical Circular Buffer task |
| Live GRPO readiness | `CONDITIONALLY READY`: live reward wiring must preserve E03 as the terminal gate |
| Validation date | 2026-08-23 |

## Step 1: Replay real model outputs against the existing verifier

The audit preserved five exact source snapshots from the four Midband-RL-v2 trials: three failed candidates and the two candidates that passed the official task. Trial 1 collapsed empty and full into `head == tail`; trial 2 first defined every template member in both editable files; trial 4 incremented the item count after a full-buffer overwrite. Source, chat, result, checkpoint, Aider-control, and archive identities are pinned in `failure_gap_manifest.json`.

The pre-audit contract authenticated only `circular_buffer.h` and supplied no implementation file to the official build. It therefore marked the duplicate-definition candidate as a pass even though the real evaluation failed to compile it. Binding both editable files and compiling `circular_buffer.cpp` closed that single missed-failure gap: the corrected E03 produces three agreement-fails and two agreement-passes, with no missed failure and no restriction.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Source corpus | Exact Midband outputs | PASS: 5 snapshots from 4 trials; every candidate hash matches | Rehash `validation/cases/midband_rl_v2_*` | Manifest SHA-256 `ed49063f82417f2b30fcb73b8e1dd6edc20d6b991a3cfcfa380139b282bfefa8` |
| Trial 1 final | Empty/full state alias | FAIL: 1/16 official tests; all five current policies fail | Replay saved header and implementation | E04 isolates new/full/released lifecycle |
| Trial 2 turn 1 | Duplicate template definitions | Real source FAIL; pre-audit E03 false pass | Replay with baseline contract | `baseline_classification=missed_failure` |
| Trial 2 turn 2 | Corrected definition placement | PASS: 60/60 assertions | Replay both editable files | All 15 current kernels pass |
| Trial 3 turn 1 | Independent valid implementation | PASS: 60/60 assertions | Replay both editable files | All 15 current kernels pass |
| Trial 4 final | Count increment after full overwrite | FAIL: 55/57 assertions; E03 and E05 fail | Replay saved candidate | E05 vector `[-1,-1,+1]` pinpoints overwrite/fullness |
| Contract correction | Bind actual editable/build boundary | Baseline: 1 miss; current: 0 misses, 0 restrictions | Run `run_failure_gap_audit.py` in pinned image | Baseline SHA `da35ac04…8774`; current SHA `e87cee9b…a42` |
| Failure-gap receipt | Machine-readable replay | PASS: baseline `2 fail/2 pass/1 miss`; current `3 fail/2 pass` | Rehash saved receipt | SHA-256 `0903759a2288a09cd7da74c99a3859556a9a8827a28552752b8fb6cc3a46ec95` |

## Step 2: Protect valid implementations and avoid unnecessary policy growth

The canonical reference plus two structurally different real Midband solutions were used as positive controls. They use different include guards, state layouts, move behavior, definition styles, and private field names; all three passed E01–E05 with the full `+15/15` vector. This guards against rewarding one reference shape or adding prompt rules that would reject valid ring-buffer designs.

The package structure also passed: five nonempty policy files pair one-to-one with five AST-valid verifiers, every declared `CB-E0x` ID matches, and all 15 expected kernels execute. Because E04 and E05 already distinguish the exact observed state-machine failures, the evidence supports no new policy; retaining the focused five-policy set minimizes context pollution and over-restriction.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Canonical reference | Perfectly formed positive control | PASS: E01–E05, 15/15 kernels | Run `reference_positive` | Uses pinned `.meta/example.h` plus inert implementation unit |
| Midband trial 2 repair | Count-based ring implementation | PASS: E01–E05, 15/15 | Run `midband_trial_2_turn_2_positive` | Real official-positive source |
| Midband trial 3 | Move-aware alternate implementation | PASS: E01–E05, 15/15 | Run `midband_trial_3_turn_1_positive` | Real official-positive source |
| Positive acceptance | Valid diversity boundary | PASS: 3/3 implementations × 5 policies | Compare policy vectors | No observed restriction |
| Policy sufficiency | Context/policy restraint | Existing E04 and E05 cover all logged semantic classes | Map real failures to policy vectors | Do not add another policy without a new missed-failure sample |
| Package structure | Pairing, IDs, syntax, inventory | PASS: 5/5 pairs and 15 kernels | Run `run_structure_validation.py` | Receipt SHA-256 `5cb623b1b7c9b0b6d232a07bfba43e0b406005f39468ca490dd3f056671c5dd1` |
| Protected instruction asset | Exact Midband task contract | SHA-256 `8501cd0234269a91f04d4c0c8aa1f7a1ee7896db4fd365a2743c5928df769134` | Rehash `validation/fixed/instructions.md` | Prevents replay against older instructions |

## Step 3: Reject defects and separate evaluator faults from model reward

The three real failed candidates and a controlled overwrite-head mutant all failed E03 and at least one shaped policy. The overwrite-count case is especially useful: E01, E02, and E04 pass while E05 fails two exact kernels, providing granular reward without pretending API success is terminal correctness. The controlled mutant independently confirms the same overwrite boundary.

Changing one byte of the official test or selecting a nonexistent compiler returned `INVALID`, never candidate `-1`. A fresh reference replay reproduced all five `pass` decisions and every `[+1,+1,+1]` vector, while source digests stayed unchanged for all eight candidate runs; these results establish evaluator integrity, repeatability, and source immutability for the pinned campaign.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Head/tail alias | Real state-machine failure | E01–E05 all FAIL | Run `head_tail_alias_failure` | Candidate-caused failure |
| Duplicate definitions | Real two-file build failure | E01–E05 all FAIL after contract correction | Run `duplicate_definitions_failure` | Previously missed by old contract |
| Overwrite count | Real partial semantic failure | E01/E02/E04 PASS; E03/E05 FAIL | Run `overwrite_count_failure` | Confirms shaped versus terminal separation |
| Overwrite-head mutant | Controlled independent defect | E01/E04 PASS; E02/E03/E05 FAIL | Run `overwrite_head_mutant` | No surviving controlled mutant |
| Tampered official test | Evaluator-integrity fault | `INVALID`: fixed-asset hash mismatch | Run invalid control | Never project as model `-1` |
| Missing compiler | Infrastructure fault | `INVALID`: compiler unavailable | Run invalid control | Rerun sample after infrastructure recovery |
| Source immutability | Verifier side-effect control | PASS: unchanged for 8/8 candidate runs | Compare before/after SHA-256 | Recorded per candidate in control receipt |
| Repeatability | Independent decision replay | PASS: 5/5 policies reproduce status and kernel vectors | Compare reference and repeat | Every vector remains `[+1,+1,+1]` |
| Control receipt | Complete campaign evidence | PASS: 3 positives, 4 defects, 2 invalid controls | Rehash saved receipt | SHA-256 `4985472b64c78e1f58c470c7417d90996403c058fdfa45a3cd23fbc8c31a9feb` |

## Final conclusion

The Circular Buffer verifier package is `READY` for its pinned canonical task. The evidence-driven change is limited to the necessary two-file contract correction; no new policy was added. Live GRPO remains `CONDITIONALLY READY` until its reward adapter is separately shown to preserve E01/E02/E04/E05 as shaped signals, require the complete E03 official gate for terminal success, and discard `INVALID` samples rather than penalizing the model.
