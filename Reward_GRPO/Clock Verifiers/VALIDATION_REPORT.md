# Clock Verifier Validation Report

| Report field | Value |
|---|---|
| Topic | Clock |
| Source evaluation | `execution-bank-RL-v2-think-r2/fixed26-mt2-4x-20260818` |
| Source checkpoint | `execution-bank-RL-v2-think-r2/checkpoints/grpo_lora_r16/iter_0000019/adapter` |
| Source outcomes | pass@1 `2/4`; pass by turn 2 `2/4` |
| Validation image | `glm47-reward-grpo-bank-account@sha256:e4d1090d07cab73e5c4137637beccebe1dac0f6aa440e7d4cbfc466c4f226932` |
| Compiler | GCC `13.3.0` |
| Policies and kernels | 5 policy/verifier pairs; 15 candidate kernels |
| Verifier-package readiness | `READY` for the pinned canonical Clock task |
| Live GRPO readiness | `CONDITIONALLY READY`: live reward wiring must preserve E03 as the terminal gate |
| Validation date | 2026-08-23 |

## Step 1: Replay real model outputs against the current verifier

The audit preserved six exact candidates from four Midband-RL-v2 trials. Trials 2 and 3 passed on their first official attempt. Trial 1 first emitted `24:00` for midnight and compared raw overflow hours, then its repair duplicated four definitions between the header and implementation. Trial 4 first emitted `24:00`/`24:01` and compared raw hours, then its repair illegally mutated instance state in a static factory and a const string observer.

The unchanged E01–E05 pack classified all six snapshots correctly: four agreement-fails and two agreement-passes, with zero missed failures and zero restrictions. E02/E04 isolate both normalization failures; E01/E05 join them after the invalid repair shapes; E03 remains the authoritative full-suite gate. Because every observed failure already reaches specific reward boundaries, no policy or verifier change is supported by this evidence.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Source corpus | Exact Midband outputs | PASS: 6 snapshots from 4 trials; candidate hashes match | Rehash `validation/cases/midband_rl_v2_*` | Manifest SHA-256 `06d748ebad0b91c1d0430901b1a235a662f401e5a5a796db6d9d5b4ca9bc8834` |
| Trial 1 turn 1 | Constructor not normalized; equality uses raw minutes | FAIL: `00:00→24:00`, `10:37≠34:37`; 21/23 assertions | Replay E02/E03/E04 | Vectors expose normalization and equality separately |
| Trial 1 turn 2 | Duplicate inline/out-of-line definitions | FAIL at compile: conversion, equality, helper, and `operator!=` redefined | Replay all policies | E01–E05 all fail |
| Trial 2 turn 1 | Independent positive | PASS official task | Replay saved sources | E01–E05 all pass, 15/15 |
| Trial 3 turn 1 | Independent positive | PASS official task | Replay saved sources | E01–E05 all pass, 15/15 |
| Trial 4 turn 1 | No modulo-day normalization | FAIL: `24:00`, `24:01`, overflow inequality; 10/13 assertions | Replay E02/E03/E04 | E01 and E05 correctly retain partial credit |
| Trial 4 turn 2 | Static factory/const observer misuse | FAIL at compile: illegal instance access and const mutation | Replay all policies | E01–E05 all fail |
| Gap classification | Existing-verifier coverage | PASS: `agreement_fail=4`, `agreement_pass=2`, misses/restrictions `0/0` | Run `run_failure_gap_audit.py` | Receipt SHA-256 `e90197288812cde61aaaa755d2935f85275908678eaaa438d6e7dcd5c174648b` |

## Step 2: Protect valid implementations and keep policies focused

The official reference and the two real Midband successes form three positive controls. They vary their state representation, normalization helper, header style, construction path, and private names, yet all three pass every policy with a `+15/15` total. This confirms that the pack rewards the public clock contract and normalized behavior rather than one reference implementation.

Structure validation also passed: five nonempty policies pair exactly with five AST-valid verifiers, every `CL-E0x` declaration matches, and all 15 kernels are represented. E04 already expresses the logged modulo-day failures and E05 already covers factory, observer, and linkage discipline, so a sixth policy would add context without a new empirical boundary.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Canonical reference | Perfectly formed positive control | PASS: E01–E05, 15/15 | Run `reference_positive` | Uses pinned `.meta/example.h/.cpp` |
| Midband trial 2 | Alternate valid clock | PASS: E01–E05, 15/15 | Run `midband_trial_2_positive` | Real official-positive source |
| Midband trial 3 | Second alternate valid clock | PASS: E01–E05, 15/15 | Run `midband_trial_3_positive` | Real official-positive source |
| Positive acceptance | Valid diversity boundary | PASS: 3/3 implementations × 5 policies | Compare all policy vectors | No observed restriction |
| Policy sufficiency | Context/policy restraint | E04 catches normalization; E05 catches repair shape | Map real failures to vectors | Add nothing without a new missed failure |
| Package structure | Pairing, IDs, syntax, inventory | PASS: 5/5 pairs and 15 kernels | Run `run_structure_validation.py` | Receipt SHA-256 `772a7dc22135fa144fcf55cc595c360ba035a02ec6dd84a8c202c5b21cf32019` |
| Protected instructions | Exact source-evaluation contract | SHA-256 `878669626ebe9c4e368e358e79e2ad94ab95dec3760a74afdce9869b14c9fe37` | Rehash `validation/fixed/instructions.md` | Prevents older-task replay |

## Step 3: Reject defects and distinguish evaluator invalidity

All four real failures are rejected by E03 and at least two shaped policies. A controlled reference mutation changes `plus(minutes)` to add one extra minute; E01 still passes the exact API, while E02, E03, E04, and E05 reject the wrong arithmetic. This is the intended reward shape: usable structural credit without terminal acceptance of a semantic defect.

Tampering with the official test or selecting a nonexistent compiler returns `INVALID`, never candidate `-1`. A fresh reference run repeats all five pass decisions and `[+1,+1,+1]` vectors, while candidate source hashes remain unchanged across all nine candidate runs; evaluator integrity, repeatability, and source immutability are therefore evidenced for this pinned package.

| Component or category | Role or failure pattern | Evidence or current status | How to verify | Files, controls, or next action |
|---|---|---|---|---|
| Trial 1 semantic defect | Missing canonical construction/equality | E02/E03/E04 FAIL; E01/E05 PASS | Run `trial_1_normalization_failure` | Granular partial reward retained |
| Trial 1 repair defect | Duplicate definitions | E01–E05 all FAIL | Run `trial_1_duplicate_definitions_failure` | Candidate build failure |
| Trial 4 semantic defect | Missing canonical construction/arithmetic/equality | E02/E03/E04 FAIL; E01/E05 PASS | Run `trial_4_normalization_failure` | Granular partial reward retained |
| Trial 4 repair defect | Static/const object-model violations | E01–E05 all FAIL | Run `trial_4_static_const_repair_failure` | Candidate build failure |
| Plus-one mutant | Independent arithmetic defect | E01 PASS; E02/E03/E04/E05 FAIL | Run `plus_one_minute_mutant` | No surviving controlled mutant |
| Tampered official test | Evaluator-integrity fault | `INVALID`: fixed-asset hash mismatch | Run invalid control | Never emit model `-1` |
| Missing compiler | Infrastructure fault | `INVALID`: compiler unavailable | Run invalid control | Rerun after infrastructure recovery |
| Source immutability | Verifier side-effect control | PASS: unchanged for 9/9 candidate runs | Compare before/after hashes | Recorded in control receipt |
| Repeatability | Independent reference replay | PASS: 5/5 decisions and vectors equal | Compare reference/repeat | Every vector remains `[+1,+1,+1]` |
| Control receipt | Complete campaign evidence | PASS: 3 positives, 5 defects, 2 invalid controls | Rehash saved receipt | SHA-256 `2adfcf38339c3c734c802e59a5bb2403a3e3dc89ea4722e1fb428224f6a4f13c` |

## Final conclusion

The Clock verifier package is `READY` for its pinned canonical task with no code or policy change required. Live GRPO remains `CONDITIONALLY READY` until its reward adapter is separately shown to use E01/E02/E04/E05 only as shaped evidence, require all of E03 for terminal success, and discard `INVALID` evaluator samples rather than assigning negative model reward.
