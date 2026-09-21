# Amazon Improved Task 002 — MiniMax M3 Evaluation Runs

<style>
body { font-size: 12px; }
table { font-size: 10px; border-collapse: collapse; width: 100%; table-layout: fixed; }
th, td { border: 1px solid #999; padding: 3px 5px; word-wrap: break-word; overflow-wrap: anywhere; }
code { font-size: 9px; word-break: break-all; }
</style>

Environment: [devjangid-wootzapp/android-envs](https://app.primeintellect.ai/dashboard/environments/devjangid-wootzapp/android-envs) — version `1.1.30`

Completed hosted evaluations: [`o167mh3pi2u9lfnzjd3h54qi`](https://app.primeintellect.ai/dashboard/evaluations/o167mh3pi2u9lfnzjd3h54qi) and [`bsvz9uou86hdthch6vi7pcgg`](https://app.primeintellect.ai/dashboard/evaluations/bsvz9uou86hdthch6vi7pcgg)

Third hosted evaluation, still running when this report was created: [`hkzcf2mvzrylrlr6rbcubqk7`](https://app.primeintellect.ai/dashboard/evaluations/hkzcf2mvzrylrlr6rbcubqk7)

| Evaluation group | Completed | PASS | Non-PASS | Observed pass count |
|---|---:|---:|---:|---:|
| Current completed Task 2 attempts | 2 | 1 | 1 | **1/2 = 50.0%** |

The requested three-attempt result is not final yet. This report counts only the two terminal, valid Prime evaluations and does not treat the running third evaluation as PASS, FAIL, or INVALID.

## Completed attempts

| # | Run / evaluation ID | Stages | Verdict | Reason | Eval | Live viewer |
|---|---|---|---|---|---|---|
| 1 | `o167mh3pi2u9lfnzjd3h54qi` | 9/9 | PASS (1) | Exact outcome and all six strict checks PASS; all 34 action-policy baselines PASS and all 34 policies meet the frozen 0.8 optimization cutoff | [open](https://app.primeintellect.ai/dashboard/evaluations/o167mh3pi2u9lfnzjd3h54qi) | Hosted viewer expired |
| 2 | `bsvz9uou86hdthch6vi7pcgg` | 9/9 | FAIL (-1) | Exact outcome, required actions, and all 34 policy gates PASS, but strict `action_audit` fails with `REQUIRED_CLAIM_UNMET` | [open](https://app.primeintellect.ai/dashboard/evaluations/bsvz9uou86hdthch6vi7pcgg) | Hosted viewer expired |

Both records are public Prime-hosted evaluations. They used `minimax/minimax-m3`, temperature `0.6`, one rollout at a time, software emulation, and the `peach_action_budget_v1` rubric. Both completed all nine task stages and satisfied the mandatory 0.5 baseline for every required action policy. Attempt 2 is a verifier FAIL, not an infrastructure INVALID.

## Verifier and runtime details

| Check | Attempt 1 | Attempt 2 | Boundary |
|---|---:|---:|---:|
| Required policy baselines | 34/34 — PASS | 34/34 — PASS | 34/34 must score at least 0.5 |
| Optimized policies | 34/34 — PASS | 34/34 — PASS | At least 28/34 at or above 0.8 |
| Step-optimization score | 100.0% | 100.0% | At least 28/34 optimized policies |
| Optimizer-check score | 136/170 = 80.0% | 102/170 = 60.0% | Diagnostic aggregate |
| Favourite taps | 25 — PASS | 27 — FAIL | ≤25 |
| Selection taps | 9 — PASS | 9 — PASS | ≤9 |
| Total actions | 45 — PASS | 49 — PASS | ≤50 |
| Completion tokens | 5,600 — PASS | 6,615 — PASS | ≤8,000 |
| Model-request time | 122.31 s — FAIL | 158.82 s — FAIL | ≤45 s |
| Strict checks | 6/6 PASS | 5/6 PASS | 6/6 required |
| Completed task stages | 9/9 | 9/9 | 9/9 required |
| Total elapsed time | 2,321.16 s | 2,273.66 s | Diagnostic |
| Recorded inference cost | $0.0630 | $0.0411 | Diagnostic |

## Evidence recorded per evaluation

Each completed evaluation has a GitHub-hosted neutral evidence ZIP. The GitHub ZIP contains its authoritative verifier receipt, the screenshot retained in the public sample, and an immutable reference to the real Android MP4 inside the verified Prime controller archive. Credentials and model transcripts are not included.

| # | Verdict | GitHub evidence ZIP (SHA-256) | Prime source archive | Android video SHA-256 | Eval |
|---|---|---|---|---|---|
| 1 | PASS | [evidence.zip (`9dde88b6b1e7cf1feaba9fd15c4116d3d4928962f36e87acf2a2271d282fb7c2`)](https://raw.githubusercontent.com/Teraformer09/browser-is-all-you-need/refs/heads/Android-ADK-Verifiers/eval/evidence/o167mh3pi2u9lfnzjd3h54qi/evidence.zip) | `beb7fa36bd907396a68176df20416d38ed41de6f8cd9a12aca63b5d1b75e0d88` | `35d93738bf0cafa73e89c7fc941e9213748ec7bab014346d93f1fa1b55fc182e` | [open](https://app.primeintellect.ai/dashboard/evaluations/o167mh3pi2u9lfnzjd3h54qi) |
| 2 | FAIL | [evidence.zip (`b99b2350fb37c6669cd8bbe2dc9942f7dc770a2d2429497cb498075c0b9cef2a`)](https://raw.githubusercontent.com/Teraformer09/browser-is-all-you-need/refs/heads/Android-ADK-Verifiers/eval/evidence/bsvz9uou86hdthch6vi7pcgg/evidence.zip) | `9f72a817ea32731b35f8f6da5192983881bd5fe93229aacdb798d4af237832d2` | `3fdee77200190513680672156e2f13e6085c0ee241b3d506202d1813f63c8361` | [open](https://app.primeintellect.ai/dashboard/evaluations/bsvz9uou86hdthch6vi7pcgg) |

### What each GitHub evidence ZIP contains

| File / path | Kind | Details |
|---|---|---|
| `verifier_receipt.json` | Verifier receipt | Final reward, verdict, six strict checks, 34 policy scores, optimizer results, reason codes, policy gate, and step-optimization score. |
| `screenshots/000.png` | Retained screenshot | Android UI screenshot retained inline by the public Prime sample. The complete ordered frame set remains in the verified Prime source archive. |
| `video/reference.json` | Video evidence reference | Evaluation ID, immutable MP4 path, media type and SHA-256, plus the verified Prime source-archive size and SHA-256. |

The authoritative Prime source archives contain the genuine Android `video/screen-recording.mp4` recordings. Prime marks both archives as `verified_prime_controller_artifact`; inline media is omitted from the dashboard because of the dashboard size limit. The current directly verified result is one PASS and one FAIL across two completed attempts. Attempt 3 remains outside the denominator until it reaches a terminal status.
