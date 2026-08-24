# Parallel Letter Frequency Verifier Validation Report

| Report field | Value |
|---|---|
| Topic | Parallel Letter Frequency |
| Source evaluation | `execution-bank-RL-v2-think-r2/fixed26-mt2-4x-20260818` |
| Source checkpoint | `execution-bank-RL-v2-think-r2/checkpoints/grpo_lora_r16/iter_0000019/adapter` |
| Source outcomes | pass@1 `2/4`; pass by turn 2 `2/4` |
| Pinned source overlay | SHA-256 `241b469203880134a8931c9df45f838a817a37430df5f02267ee3cf2ebf57ba5` |
| Official test | SHA-256 `9f0625d18d5ad5a04136c92d3064456a3c3e9e7847f4810f0c75f6d9db49ea5e` |
| Validation image | `glm47-reward-grpo-bank-account@sha256:e4d1090d07cab73e5c4137637beccebe1dac0f6aa440e7d4cbfc466c4f226932` |
| Compiler | GCC `13.3.0` |
| Policies and kernels | 5 policy/verifier pairs; 15 candidate kernels |
| Verifier-package readiness | `READY` for the pinned canonical task |
| Live GRPO readiness | `CONDITIONALLY READY`: E03 must gate terminal success and `INVALID` samples must be discarded |
| Validation date | 2026-08-23 |

## Step 1: Replay real model outputs against the current verifier

The audit preserved six exact candidates from the four Midband-RL-v2 trials. Trials 1 and 4 passed on turn one. Trial 2 first lacked both `<execution>` and `<cctype>`, then added only `<cctype>` and still failed to declare `std::execution`. Trial 3 first lacked `<cctype>`, then compiled but aborted because it created worker ranges past `texts.end()`; that final implementation also merged into a shared map without synchronization and used `isalnum`.

The unchanged E01–E05 package classified two agreement-passes and four agreement-fails, with zero missed failures and zero restrictions. E01 preserves API credit for the failed candidates, while E04/E05 distinguish Trial 3's compiled runtime/semantic defects from Trial 2's dependency failure. The real-output replay therefore does not justify another policy.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Source corpus | Exact Midband candidates | PASS: 6 snapshots from 4 trials; every source hash pinned | Rehash `validation/cases/midband_rl_v2_*` | Manifest SHA-256 `7639c00dee5dd2c56f72bc587faca6f1944d15284202292943992cdadf385131` |
| Trial 1 final | Execution-policy implementation | Agreement pass: 15/15 kernels | Replay saved final source | Valid only within the pinned no-TBB fallback environment |
| Trial 2 turn 1 | Missing `<execution>` and `<cctype>` | Agreement fail; E01 API/signature kernels 2/3 | Replay saved first response | Compile/link and every semantic policy reject it |
| Trial 2 final | Partial include repair | Agreement fail; E01 API/signature kernels 2/3 | Replay saved final source | `std::execution` remains undeclared |
| Trial 3 turn 1 | Missing `<cctype>` plus unsafe partition design | Agreement fail; E01 API/signature kernels 2/3 | Replay saved first response | Candidate cannot compile |
| Trial 3 final | Past-end ranges, runtime abort, shared-map race, digit filter | Agreement fail; E03 authenticates/builds but execution fails | Replay saved final source | E04 vector `[+1,-1,-1]`; E05 `[-1,+1,-1]` |
| Trial 4 final | Independent partial-map transform and merge | Agreement pass: 15/15 kernels | Replay saved final source | Second alternate-valid control |
| Gap classification | Current-verifier agreement | PASS: agreement pass/fail `2/4`; misses/restrictions `0/0` | Run `run_failure_gap_audit.py` | Receipt SHA-256 `0c1edb3a55fd055263b0610a9da8db9bc61844323abb679fcfa2c61fd620d08f` |

## Step 2: Protect valid implementations and keep policies focused

The canonical reference and both real Midband successes form three positive controls with different include guards, execution-policy placement, counting storage, helper structure, and merge strategy. All three pass every current policy, producing 45/45 positive kernel decisions. The package accepts observed implementation diversity instead of requiring the reference source shape.

Structure validation finds five nonempty policy documents paired one-to-one with five AST-valid verifiers and exactly 15 candidate kernels. E01 covers API/build, E02 independent semantics, E03 the authenticated official terminal suite, E04 dependencies/filtering, and E05 aggregation/repeatability. These boundaries cover every observed failure without adding unrelated concurrency or implementation-style restrictions.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Canonical reference | Perfectly formed positive control | PASS: 15/15 | Run `reference_positive` | Pinned `.meta/example.h/.cpp` |
| Midband trial 1 | Real alternate-valid control | PASS: 15/15 | Run `midband_trial_1_positive` | Shared array is sequential under the pinned backend fallback |
| Midband trial 4 | Second real alternate-valid control | PASS: 15/15 | Run `midband_trial_4_positive` | Independent partial maps and sequential merge |
| Positive acceptance | Valid diversity boundary | PASS: 3 implementations × 15 kernels = 45/45 | Compare all policy vectors | No observed false restriction |
| E01 | Exact API, compile and link | 3 independent kernels | Inspect `verifier_01_*.py` receipt | Shaped credit; never terminal alone |
| E02/E04/E05 | Task-specific shaped semantics | 9 independent kernels | Inspect per-kernel vectors | Filters, aggregation and repeatability stay separate |
| E03 | Authenticated official behavior | 3 kernels | Inspect fixed hashes and official execution | Mandatory terminal gate |
| Package structure | Pairing, syntax, IDs and counts | PASS: 5/5 pairs; 15 kernels | Run `run_structure_validation.py` | Receipt SHA-256 `9963f0e042e626d0f28f9724aa380323903ef8c1fc3359d6e6bff9173635555c` |
| Policy restraint | Avoid context pollution | No new policy supported by real replay | Require a miss or restriction before expansion | Keep current five policies |

## Step 3: Reject focused defects and distinguish evaluator invalidity

A digit-counting mutation preserves the complete API and aggregation behavior but fails only E02's filter slice, E03 execution, and E04's nonletter slice. A lost-aggregation mutation also preserves E01, then fails the aggregation-sensitive slices of E02, E03, E04, and E05. Both mutations are rejected without collapsing all earned evidence into one binary score.

Tampering with the official test and removing the compiler both return `INVALID`, never candidate `-1`. A fresh reference repeat reproduces all five policy decisions and all 15 kernel scores, and all ten candidate executions preserve source hashes. Candidate failure, evaluator failure, source immutability, and repeatability are therefore separated for the tested boundary.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Trial 2 dependency defect | Missing declaration ownership | KILLED by E01–E05 terminal/status checks | Replay both Trial 2 turns | API kernels retain legitimate partial credit |
| Trial 3 runtime defect | Invalid partition ranges and unsafe shared merge | KILLED by E01–E05; E03 build passes, run fails | Replay Trial 3 final | E04/E05 retain passing subchecks |
| Digit-counting mutant | `isalnum` admits digits | E01/E05 PASS; E02/E03/E04 FAIL | Run `digit_counting_mutant` | Exact filter boundary isolated |
| Lost-aggregation mutant | Later partial maps overwrite earlier counts | E01 PASS; E02–E05 FAIL | Run `lost_aggregation_mutant` | Aggregation boundary isolated |
| Tampered official test | Evaluator-integrity fault | `INVALID`: protected test hash mismatch | Run invalid control | Never convert to model `-1` |
| Missing compiler | Infrastructure fault | `INVALID`: compiler unavailable | Run invalid control | Rerun after infrastructure recovery |
| Source immutability | Verifier side-effect control | PASS for all 10 candidate executions | Compare before/after hashes | No candidate source bytes changed |
| Repeatability | Independent canonical replay | PASS: 5/5 policies and 15/15 kernel vectors equal | Compare reference/repeat | Runtime paths excluded |
| Control receipt | Positive, defect, invalid and repeat evidence | PASS: 3 positives, 6 defects, 2 invalid controls, 1 repeat | Rehash saved receipt | SHA-256 `cd1243c97d9ac2f8ebf29ce7fa000c9f050832e05bd29afc958e0d2d8ac163ac` |

## Final conclusion

The Parallel Letter Frequency verifier package is `READY` for the pinned canonical task with no policy or verifier change required. Live GRPO is `CONDITIONALLY READY` until reward wiring proves that all 15 kernels execute independently, E03 gates terminal success, and evaluator `INVALID` samples are discarded rather than scored against the model.
