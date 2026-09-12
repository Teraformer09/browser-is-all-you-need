# DemoCart — MiniMax M3 (temperature 0) Evaluation Runs

<style>
body { font-size: 12px; }
table { font-size: 10px; border-collapse: collapse; width: 100%; table-layout: fixed; }
th, td { border: 1px solid #999; padding: 3px 5px; word-wrap: break-word; overflow-wrap: anywhere; }
code { font-size: 9px; word-break: break-all; }
</style>


Environment: [devjangid-wootzapp/amazon-cart-2](https://app.primeintellect.ai/dashboard/environments/devjangid-wootzapp/amazon-cart-2)

## Final series result (n=12)

| Metric | Value |
|---|---|
| **pass@1** | **7/12 = 58.3%** |
| **pass@3** | **95.45%** (1 − C(5,3)/C(12,3)) |
| Assessable-only pass rate | 7/9 = 77.8% |
| PASS / FAIL / INVALID | 7 / 2 / 3 |
| Version | 0.6.2 (reported final; INVALIDs tagged, never relabeled) |

## All 12 attempts

| # | Run / evaluation ID | Stages | Verdict | Reason | Eval | Live viewer (expired) |
|---|---|---|---|---|---|---|
| 1 | `q65p9ohkaxqn862qvzyg7stz` | 6/6 | PASS (1) | Exact cart; all six strict checks PASS | [open](https://app.primeintellect.ai/dashboard/evaluations/q65p9ohkaxqn862qvzyg7stz) | [open](https://t-2-f742c42e20a21de3.tunnel.pinfra.io) |
| 2 | `qeh676mq27avcug1afehes5x` | 0/6 | INVALID (0) | Task app not visible mid-episode (infra) | [open](https://app.primeintellect.ai/dashboard/evaluations/qeh676mq27avcug1afehes5x) | [open](https://t-1-2f0b73f01e8d8320.tunnel.pinfra.io) |
| 3 | `ajraysr9tlast83py4qbtwuv` | 6/6 | FAIL (-1) | action_audit: 2 rejected focus taps; cart exact | [open](https://app.primeintellect.ai/dashboard/evaluations/ajraysr9tlast83py4qbtwuv) | [open](https://t-2-29d5df0e0a3c9d68.tunnel.pinfra.io) |
| 4 | `jwfc61cj7jrqekeauis8cxzb` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/jwfc61cj7jrqekeauis8cxzb) | [open](https://t-1-291b2d7b71966899.tunnel.pinfra.io) |
| 5 | `x5aahb268gxy73dn19hil2jf` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/x5aahb268gxy73dn19hil2jf) | [open](https://t-1-a1ca05ded27f713c.tunnel.pinfra.io) |
| 6 | `eaur3i6zlwhydqs3s5l8w3c1` | 6/6 | PASS (1) | Exact cart; all checks PASS (13 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/eaur3i6zlwhydqs3s5l8w3c1) | [open](https://t-0-fc7cd7ae8cf882a4.tunnel.pinfra.io) |
| 7 | `fo97qft38o9x66fcwe0zsxss` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/fo97qft38o9x66fcwe0zsxss) | [open](https://t-2-15c9ed937efab2c9.tunnel.pinfra.io) |
| 8 | `mkkez6ffpcfz7r4rucncsnvc` | 6/6 | INVALID (0) | action_audit: ADB_TRACE_UNASSESSABLE; cart exact | [open](https://app.primeintellect.ai/dashboard/evaluations/mkkez6ffpcfz7r4rucncsnvc) | [open](https://t-0-778ca0629bce25ce.tunnel.pinfra.io) |
| 9 | `akj8rxbxldaki2ydj50mc15s` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/akj8rxbxldaki2ydj50mc15s) | [open](https://t-0-0ef5f99b055d3273.tunnel.pinfra.io) |
| 10 | `ir02wn8tlk2dqvwnpeafdgor` | 6/6 | FAIL (-1) | action_audit: 1 rejected focus tap; cart exact | [open](https://app.primeintellect.ai/dashboard/evaluations/ir02wn8tlk2dqvwnpeafdgor) | [open](https://t-0-27a3a3adb41e4e2f.tunnel.pinfra.io) |
| 11 | `ylg5z2g1oqy2p19nm3abwsje` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/ylg5z2g1oqy2p19nm3abwsje) | [open](https://t-0-189b97ea6f2de069.tunnel.pinfra.io) |
| 12 | `cgndyg2lfe2itadcmzt25nvi` | 6/6 | INVALID (0) | action_audit: FOCUS_PROBE_COMMANDS; cart exact | [open](https://app.primeintellect.ai/dashboard/evaluations/cgndyg2lfe2itadcmzt25nvi) | [open](https://t-0-29c07612d4ac947b.tunnel.pinfra.io) |

All runs: MiniMax M3, temperature 0, amazon-cart-2 v0.6.2, single attempts one by one. The two pre-model provisioning INVALID retries (zero model calls) are excluded from n per request; recorded in the series ledger.

## Evidence stored on Prime Intellect (per evaluation)

Each eval has its **own evidence.zip artifact** (12 separate artifacts, no shared folder). **Honest access note:** the zips live in Prime's **private artifact store** — there is no public download URL for the zip file itself (API 404s on all artifact endpoints; the dashboard has no zip-download route). The links below open the eval page, whose transcript shows the 12–13 inline screenshots and verdict/log content. A locally reconstructable bundle (hosted_verdict.json, provenance.json, installed_apk.json, checkpoints, per-step screenshots) can be exported from the API on request; per-frame `ui.xml`/`database.sqlite` and the MP4 bytes remain remote-only.

| # | Verdict | evidence.zip artifact (SHA-256 path) | Eval |
|---|---|---|---|
| 1 | PASS | [`evidence.zip` (468a35beda5b…)](https://app.primeintellect.ai/dashboard/evaluations/q65p9ohkaxqn862qvzyg7stz) | [open](https://app.primeintellect.ai/dashboard/evaluations/q65p9ohkaxqn862qvzyg7stz) |
| 2 | INVALID | [`evidence.zip` (b2ca67344574…)](https://app.primeintellect.ai/dashboard/evaluations/qeh676mq27avcug1afehes5x) | [open](https://app.primeintellect.ai/dashboard/evaluations/qeh676mq27avcug1afehes5x) |
| 3 | FAIL | [`evidence.zip` (bbe11bb9ebb6…)](https://app.primeintellect.ai/dashboard/evaluations/ajraysr9tlast83py4qbtwuv) | [open](https://app.primeintellect.ai/dashboard/evaluations/ajraysr9tlast83py4qbtwuv) |
| 4 | PASS | [`evidence.zip` (85d7d2f61241…)](https://app.primeintellect.ai/dashboard/evaluations/jwfc61cj7jrqekeauis8cxzb) | [open](https://app.primeintellect.ai/dashboard/evaluations/jwfc61cj7jrqekeauis8cxzb) |
| 5 | PASS | [`evidence.zip` (2584f60205e2…)](https://app.primeintellect.ai/dashboard/evaluations/x5aahb268gxy73dn19hil2jf) | [open](https://app.primeintellect.ai/dashboard/evaluations/x5aahb268gxy73dn19hil2jf) |
| 6 | PASS | [`evidence.zip` (55511a6a9f4a…)](https://app.primeintellect.ai/dashboard/evaluations/eaur3i6zlwhydqs3s5l8w3c1) | [open](https://app.primeintellect.ai/dashboard/evaluations/eaur3i6zlwhydqs3s5l8w3c1) |
| 7 | PASS | [`evidence.zip` (a6d1b92a4879…)](https://app.primeintellect.ai/dashboard/evaluations/fo97qft38o9x66fcwe0zsxss) | [open](https://app.primeintellect.ai/dashboard/evaluations/fo97qft38o9x66fcwe0zsxss) |
| 8 | INVALID | [`evidence.zip` (9eabe42894e6…)](https://app.primeintellect.ai/dashboard/evaluations/mkkez6ffpcfz7r4rucncsnvc) | [open](https://app.primeintellect.ai/dashboard/evaluations/mkkez6ffpcfz7r4rucncsnvc) |
| 9 | PASS | [`evidence.zip` (3dc08a069665…)](https://app.primeintellect.ai/dashboard/evaluations/akj8rxbxldaki2ydj50mc15s) | [open](https://app.primeintellect.ai/dashboard/evaluations/akj8rxbxldaki2ydj50mc15s) |
| 10 | FAIL | [`evidence.zip` (43fb45bb1f01…)](https://app.primeintellect.ai/dashboard/evaluations/ir02wn8tlk2dqvwnpeafdgor) | [open](https://app.primeintellect.ai/dashboard/evaluations/ir02wn8tlk2dqvwnpeafdgor) |
| 11 | PASS | [`evidence.zip` (38bae102947c…)](https://app.primeintellect.ai/dashboard/evaluations/ylg5z2g1oqy2p19nm3abwsje) | [open](https://app.primeintellect.ai/dashboard/evaluations/ylg5z2g1oqy2p19nm3abwsje) |
| 12 | INVALID | [`evidence.zip` (d66b19c24158…)](https://app.primeintellect.ai/dashboard/evaluations/cgndyg2lfe2itadcmzt25nvi) | [open](https://app.primeintellect.ai/dashboard/evaluations/cgndyg2lfe2itadcmzt25nvi) |

### What each evidence.zip contains

| File / path | Kind | Details |
|---|---|---|
| `frames/NNN/screen.png` | Per-step screenshot | Original 1080x2400 PNG after every action plus initial state (12–13 per run), SHA-256 hash-bound to its checkpoint |
| `frames/NNN/ui.xml` | UI tree | Full accessibility hierarchy for that step (nodes, IDs, bounds, focus states) |
| `frames/NNN/database.sqlite` | App state | The app's SQLite snapshot at that step (cart, searches, session) |
| `frames/NNN/frame.json` | Frame receipt | Per-frame hashes, episode ID, capture attempts, consistency refs |
| `video/screen-recording.mp4` | Screen recording | Actual Android screenrecord of the episode, playback-verified, stored as artifact with SHA-256 |
| `hosted_verdict.json` | **Verifier verdict** | Final verdict: all six strict checks (status/reward/reason/evidence refs), plus the **15-policy × 75-verifier receipts** — every policy with `policy_score = 0.5 + 0.1 × passed_verifiers`, passed/failed/invalid counts, per-verifier reason codes and evidence refs |
| `provenance.json` | Code identity | Package identity, execution location, episode ID, SHA-256 of every verifier/harness source file |
| `installed_apk.json` | App identity | APK package name + SHA-256, must match the expected build |
| `checkpoints/NNN.json` | Per-step scores | Workflow stages, strict checks per step, 15-policy results with support scores, screenshot refs |
| `trajectory.jsonl`, `adb_actions.jsonl` | Action + command trace | Every model action and ADB command with return codes, phases and hashes |
| `input_readback/` | Text-delivery proof | Focus-probe XMLs and provider readbacks proving typed text reached the app |
