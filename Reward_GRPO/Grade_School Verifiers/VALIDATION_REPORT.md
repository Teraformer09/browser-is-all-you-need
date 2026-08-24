# Grade School Verifier Validation Report

| Report field | Value |
|---|---|
| Topic | Grade School |
| Source evaluation | `execution-bank-RL-v2-think-r2/fixed26-mt2-4x-20260818` |
| Source checkpoint | `execution-bank-RL-v2-think-r2/checkpoints/grpo_lora_r16/iter_0000019/adapter` |
| Source outcomes | pass@1 `2/4`; pass by turn 2 `2/4`; 1 context-exhausted trial |
| Source prompt overlay | SHA-256 `f913000d110e10de2f182ee1470765fbca95d916a8cf2735b379fc05fbf58001` |
| Verifier contract | Pristine pinned instructions SHA-256 `8dc7133cd5f0564717108757c27ad96ebadf44f03b5fde5c35b826aaeb0b4e0f`; same public API and official test bytes |
| Validation image | `glm47-reward-grpo-bank-account@sha256:e4d1090d07cab73e5c4137637beccebe1dac0f6aa440e7d4cbfc466c4f226932` |
| Compiler | GCC `13.3.0` |
| Policies and kernels | 10 policy/verifier pairs; 32 source kernels; 43 complete-campaign kernels |
| Verifier-package readiness | `READY` for the pinned canonical Grade School task |
| Live GRPO readiness | `CONDITIONALLY READY`: E05 and E06 must jointly gate semantic success; E07/E08 need authenticated bundles |
| Validation date | 2026-08-23 |

## Step 1: Replay real model outputs against the current verifier

The audit preserved five exact candidate snapshots from four Midband-RL-v2 trials. Trials 1 and 2 passed on turn one. Trial 3 defined an undeclared constructor and used `std::domain_error` without `<stdexcept>`, then produced no repair after context exhaustion. Trial 4 first used `std::set` without including `<set>` in the public header, then added that include but still used `std::invalid_argument` without `<stdexcept>`.

The unchanged E01–E06/E09 layer classified the corpus as two agreement-passes and three agreement-fails, with zero missed failures and zero restrictions. The joint E05/E06 terminal gate agrees with the official outcomes, and shaped vectors distinguish Trial 3’s valid public declarations and Trial 4’s partial header repair from a complete solution. No new Grade School policy is supported by these failures.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Source corpus | Exact Midband outputs | PASS: 5 snapshots from 4 trials; all candidate hashes pinned | Rehash `validation/cases/midband_rl_v2_*` | Manifest SHA-256 `c5fddd67757a484502e88bd603c9c0586682db13deddb2e1d46cb8079c9a3946` |
| Trial 1 turn 1 | Independent valid roster with sorted insertion | PASS: E01–E06/E09, 28/28 | Replay the saved source | Official 8/8 result retained |
| Trial 2 turn 1 | Second independent valid roster | PASS: E01–E06/E09, 28/28 | Replay the saved source | Official 8/8 result retained |
| Trial 3 turn 1/final | Undeclared constructor plus missing `<stdexcept>` | FAIL: E01/E02/E04–E06/E09; E03 preserves 3/4 API kernels | Replay the saved source | No second candidate existed after context exhaustion |
| Trial 4 turn 1 | Public header uses `std::set` without owning include | FAIL: all seven static policies | Replay reconstructed authenticated first response | E04 isolates header/dependency ownership |
| Trial 4 turn 2 | `<set>` repaired; `<stdexcept>` still missing | FAIL: E01/E02/E04–E06/E09; E03 preserves 3/4 | Replay the saved final source | Repair improves header parse but not linkage |
| Prompt boundary | Source overlay versus verifier fixture | Overlay only makes the exact API/build contract explicit; source files and official test are unchanged | Compare both files in `validation/fixed/` | Replay records both instruction hashes rather than conflating them |
| Gap classification | Current-verifier coverage | PASS: `agreement_pass=2`, `agreement_fail=3`; misses/restrictions `0/0` | Run `run_failure_gap_audit.py` | Receipt SHA-256 `f5eda225e82482d589e7c2b4344e908ed88c1bdd24e3a17d7b8e6bd195008105` |

## Step 2: Protect valid implementations and keep policies focused

The canonical reference and both real Midband successes form three positive controls with different include guards, helper choices, duplicate handling, lookup paths, and insertion implementations. All three pass every static replay policy, producing 84/84 positive kernel decisions; the verifier therefore accepts observed implementation diversity instead of requiring the reference source shape.

Structure validation pairs ten nonempty policies with ten AST-valid verifiers and exactly 43 documented implementations: 32 candidate-source kernels, five feedback kernels, and six harness-integrity kernels. E07/E08 were not fabricated for source-only replay, while E10 keeps its previously validated Clang role. The existing policy set already maps every observed failure to a concrete boundary without adding prompt context.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Canonical reference | Perfectly formed positive control | PASS: 28/28 static replay kernels | Run `reference_positive` | Uses pinned `.meta/example.h/.cpp` |
| Midband trial 1 | Real alternate-valid control | PASS: 28/28 | Run `midband_trial_1_positive` | Cross-grade duplicate handling differs from reference |
| Midband trial 2 | Second real alternate-valid control | PASS: 28/28 | Run `midband_trial_2_positive` | Uses independent find/sort implementation |
| Positive acceptance | Valid diversity boundary | PASS: 3 implementations × 28 kernels = 84/84 | Compare all policy vectors | No observed false restriction |
| E07 feedback layer | Two-turn evidence | Not applicable to source-only candidates | Supply authenticated generated/delivered feedback bundle | Run only when complete evidence exists |
| E08 harness layer | Response/tree/log integrity | Not applicable to source-only candidates | Supply authenticated Aider bundle | Never infer response integrity from source alone |
| E10 portability layer | Clang portability and clean reproduction | Retains prior package evidence; not replayed as GCC | Run in pinned Clang environment | Four candidate-source kernels |
| Package structure | Pairing, syntax, comments, documented kernel IDs | PASS: 10/10 pairs; 32 source and 43 complete kernels | Run `run_structure_validation.py` | Receipt SHA-256 `4b8b0025eacb5513669bc21516e577761535a43f8175b0899baf02120695126b` |
| Context/policy restraint | Avoid generic extra rules | Current E01/E04 catch both include failures; E05/E06 remain semantic gates | Map replay vectors to failures | Add nothing without a real missed failure or false restriction |

## Step 3: Reject defects and distinguish evaluator invalidity

All three real failed snapshots are rejected by both terminal layers. An additional API-correct unsorted-name mutation passes E01–E04 but fails E05 with `[+1,-1,-1]` and E06 with `[+1,-1,+1,+1,-1]`; this proves the reward can preserve earned build/API credit without granting semantic success to insertion-order output.

Tampering with the official test and removing the compiler both return `INVALID`, never candidate `-1`. A fresh canonical repeat reproduces all seven policy decisions and all 28 kernel scores, and every candidate source hash remains unchanged. Candidate failure, evaluator failure, immutability, and repeatability are therefore separated for the tested boundary.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Trial 3 compile defect | Constructor declaration and `<stdexcept>` ownership | KILLED by build, dependency, official, relational, and sanitizer layers | Replay Trial 3 | API declaration kernels retain legitimate partial credit |
| Trial 4 first-turn defect | Missing header-owned `<set>` | KILLED by all static policies | Replay Trial 4 turn 1 | E04 directly exposes the header boundary |
| Trial 4 final defect | Missing implementation-owned `<stdexcept>` | KILLED by E01/E02/E04–E06/E09 | Replay Trial 4 final | Header repair does not become terminal success |
| Unsorted-name mutant | API-correct semantic defect | E01–E04 PASS; E05/E06/E09 FAIL | Run `unsorted_names_mutant` | No semantic survivor |
| Tampered official test | Evaluator-integrity fault | `INVALID`: protected test hash mismatch | Run invalid control | Never convert to model `-1` |
| Missing compiler | Infrastructure fault | `INVALID`: compiler unavailable | Run invalid control | Rerun after infrastructure recovery |
| Source immutability | Verifier side-effect control | PASS for every replay and candidate control | Compare before/after hashes | No source bytes changed |
| Repeatability | Independent canonical replay | PASS: 7/7 decisions and all 28 kernel scores equal | Compare reference/repeat | Runtime and temporary paths are excluded |
| Control receipt | Positive, mutant, invalid, and repeat evidence | PASS: 3 positives, 1 semantic mutant, 2 invalid controls, 1 repeat | Rehash saved receipt | SHA-256 `e852047bfddc6c726f60f284cb5469dc18a208f1b6a39969eea1d77b98744bf4` |

## Final conclusion

The Grade School verifier package is `READY` for its pinned canonical task with no policy or verifier change required. Live GRPO is `CONDITIONALLY READY` until reward wiring proves that E01–E04 provide shaped evidence, E05 and E06 jointly gate semantic success, E07/E08 execute only on authenticated bundles, E09/E10 run under their intended schedules and toolchains, and evaluator `INVALID` samples are discarded rather than scored against the model.
