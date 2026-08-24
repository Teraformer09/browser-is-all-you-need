# Complex Numbers Verifier Validation Report

| Report field | Value |
|---|---|
| Topic | Complex Numbers |
| Source evaluation | `execution-bank-RL-v2-think-r2/fixed26-mt2-4x-20260818` |
| Source checkpoint | `execution-bank-RL-v2-think-r2/checkpoints/grpo_lora_r16/iter_0000019/adapter` |
| Source outcomes | pass@1 `0/4`; pass by turn 2 `1/4` |
| Validation image | `glm47-reward-grpo-bank-account@sha256:e4d1090d07cab73e5c4137637beccebe1dac0f6aa440e7d4cbfc466c4f226932` |
| Compiler | GCC `13.3.0` |
| Policies and kernels | 5 policy/verifier pairs; 15 candidate kernels |
| Verifier-package readiness | `READY` for the pinned canonical Complex Numbers task |
| Live GRPO readiness | `CONDITIONALLY READY`: live reward wiring must preserve E03 as the terminal gate and discard `INVALID` samples |
| Validation date | 2026-08-23 |

## Step 1: Replay real model outputs against the existing verifier

The audit preserved eight exact candidates from all four Midband-RL-v2 trials. Every first turn failed. Trials 1 and 2 repaired only part of the free-operator access surface, Trial 3 introduced header/implementation member-name drift, and only Trial 4 declared a complete legal friend surface and passed on turn 2. The authenticated source result is therefore pass@1 `0/4` and pass by turn 2 `1/4`.

The unchanged terminal E03 gate agreed with all eight official outcomes: seven agreement-fails and one agreement-pass. The positive-control comparison nevertheless exposed a shaped-policy restriction: baseline E04 required stream text `"(1,-2)"`, while neither the instructions nor official tests specify a format; the official-positive Trial 4 candidate emitted `"1 + -2i"`. This is a verifier false negative, not a model defect, and it justified relaxing that single undocumented assertion.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Source corpus | Exact Midband outputs | PASS: 8 snapshots from 4 trials; candidate hashes match | Rehash `validation/cases/midband_rl_v2_*` | Manifest SHA-256 `42d22004849588ff7d76b62e7c09ce29b5c9c3291109dd3af5ec06c0ae3d8f2e` |
| Trial 1 turn 1 | Stale member names plus private access | FAIL: implementation cannot link against its declared state | Replay E01–E05 | E01 link fails; E02–E05 expose broader failure |
| Trial 1 turn 2 | Missing friend declarations | FAIL: free operators still read private state | Replay E04/E03 | Repair does not cross the legal-access boundary |
| Trial 2 turn 1 | No legal free-operator access | FAIL | Replay E04/E03 | All three E04 kernels fail |
| Trial 2 turn 2 | Partial friendship only | FAIL: equality/stream repaired, scalar operators still private | Replay E04/E03 | Partial repair remains terminally wrong |
| Trial 3 turn 1 | No legal free-operator access | FAIL | Replay E04/E03 | All three E04 kernels fail |
| Trial 3 turn 2 | Header/implementation state drift | FAIL: `imag_` versus `imaginary_` | Replay E01–E05 | Compile/link boundary rejects it |
| Trial 4 turn 1 | No legal free-operator access | FAIL | Replay E04/E03 | All three E04 kernels fail |
| Trial 4 turn 2 | Complete legal repair | PASS official task | Replay saved sources | E01–E05 all pass after correction |
| Baseline E04 restriction | Unsupported exact stream format | CONFIRMED false negative on an official-positive candidate | Inspect baseline receipt | Receipt SHA-256 `b0cb6505e448cd9a206ec6b97186d44a73bd7a4be4b14496c7c37e2cb492f612` |

## Step 2: Correct the restriction and protect valid diversity

E04-A was changed only from exact text comparison to checking that insertion compiles, links, executes, and leaves the stream valid. Equality still distinguishes real and imaginary components, and E04-B/E04-C still verify scalar arithmetic in both operand orders. No private field name, friendship layout, or output spelling is required, which matches the pinned public contract and removes context pressure toward one reference representation.

Three independent positive controls now pass every policy and all 15 kernels: the canonical reference, the real official-positive Trial 4 repair, and a behavior-preserving reference variant with both private fields renamed. Structure validation also passes all five policy/verifier pairings, AST parsing, `CX-E0x` identities, and the complete 15-kernel inventory; no sixth policy is supported by the observed failures.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| E04 correction | Remove undocumented output spelling | PASS: only `out.str() == "(1,-2)"` was removed | Compare baseline/current E04 hashes | Baseline `36ced929…5ca1`; current `78346aa4…5008` |
| Equality surface | Preserve semantic boundary | PASS: unequal imaginary parts remain rejected | Run E04-A | Equality behavior unchanged |
| Scalar operator surface | Preserve logged repair boundary | PASS: both operand orders for `+ - * /` remain checked | Run E04-B/E04-C | Missing friendship still fails at compile time |
| Canonical reference | Perfectly formed training positive | PASS: E01–E05, 15/15 kernels | Run `reference_positive` | Protected reference sources only enter a temporary fixture |
| Midband Trial 4 | Real alternate official positive | PASS: E01–E05, 15/15 kernels | Run `midband_trial_4_positive` | Proves false restriction is removed |
| Renamed private state | Alternate-valid control | PASS: E01–E05, 15/15 kernels | Run `alternate_private_names_positive` | Proves no field-name overfit |
| Positive acceptance | Valid diversity boundary | PASS: 3/3 implementations × 5 policies | Compare policy vectors | No observed restriction remains |
| Package structure | Pairing, IDs, syntax, inventory | PASS: 5/5 pairs and 15 kernels | Run `run_structure_validation.py` | Receipt SHA-256 `4ab5bb204272d1ad7d7dee6628bae42f71bda42a5f3e742cf883439a9a5bb2a1` |
| Protected instructions | Exact evaluation contract | SHA-256 `32d74988f93a781b3b27fc6750f4f41bcdf7b4d462904389d409e9ad606063fb` | Rehash `validation/fixed/instructions.md` | Prevents replay against a different task contract |

## Step 3: Recheck defects, evaluator invalidity, and repeatability

All seven real failed snapshots remain rejected by E03 and by shaped policies after the E04 relaxation. An independent controlled mutant changes complex multiplication's real part from subtraction to addition: E01 and E04 correctly retain structural/free-operator credit, while E02, E03, and E05 reject the arithmetic error. The correction therefore removes one false negative without weakening any demonstrated defect boundary.

Tampering with the official test and selecting a nonexistent compiler both return `INVALID`, never candidate failure. A fresh reference replay repeats every policy decision and `[+1,+1,+1]` vector, and candidate hashes remain unchanged across all 12 candidate runs. The corrected failure replay again records seven agreement-fails and one agreement-pass with zero terminal misses or restrictions.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Seven real defects | Logged model-failure boundary | PASS: 7/7 terminally rejected; shaped detection present | Run saved failure cases | No observed failure was lost by the E04 correction |
| Multiplication-sign mutant | Independent semantic defect | E01/E04 PASS; E02/E03/E05 FAIL | Run `multiplication_sign_mutant` | Granular credit without terminal false pass |
| Tampered official test | Evaluator-integrity fault | `INVALID`: fixed-asset hash mismatch | Run invalid control | Never emit model `-1` |
| Missing compiler | Infrastructure fault | `INVALID`: compiler unavailable | Run invalid control | Rerun after infrastructure recovery |
| Source immutability | Verifier side-effect control | PASS: unchanged for 12/12 candidate runs | Compare before/after hashes | Recorded in control receipt |
| Repeatability | Independent reference replay | PASS: 5/5 decisions and vectors equal | Compare reference/repeat | Every vector remains `[+1,+1,+1]` |
| Current gap classification | Post-fix official agreement | PASS: `agreement_fail=7`, `agreement_pass=1`, misses/restrictions `0/0` | Run `run_failure_gap_audit.py` | Receipt SHA-256 `cbe0fe31b079471aa89b32e8c7f8fb4bc0b0c1f7358476b44786537aaf05e803` |
| Control campaign | Complete post-fix evidence | PASS: 3 positives, 8 defects, 2 invalid controls | Run `run_control_validation.py` | Receipt SHA-256 `c23364cfbc45ae848b5b8c7bd6658e84f6759374f155b02431cc87cc4a841b9d` |

## Final conclusion

The corrected Complex Numbers verifier package is `READY` for its pinned canonical task. One evidence-backed relaxation removed an undocumented exact stream-format restriction; all valid controls now pass, all real and controlled defects remain rejected, evaluator faults remain `INVALID`, and no additional policy is justified. Live GRPO is `CONDITIONALLY READY` until its reward adapter is separately shown to keep E03 mandatory for terminal success, use the other policies only for shaped reward, and discard `INVALID` samples.
