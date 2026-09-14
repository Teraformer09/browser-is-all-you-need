# DemoCart — MiniMax M3 Evaluation Runs (18 included)

<style>
body { font-size: 12px; }
table { font-size: 10px; border-collapse: collapse; width: 100%; table-layout: fixed; }
th, td { border: 1px solid #999; padding: 3px 5px; word-wrap: break-word; overflow-wrap: anywhere; }
code { font-size: 9px; word-break: break-all; }
</style>


Environments: [devjangid-wootzapp/amazon-cart-2](https://app.primeintellect.ai/dashboard/environments/devjangid-wootzapp/amazon-cart-2) and [devjangid-wootzapp/amazon-improved-task-001](https://app.primeintellect.ai/dashboard/environments/devjangid-wootzapp/amazon-improved-task-001)

| Evaluation group | n | PASS | Non-PASS | pass@3 |
|---|---:|---:|---:|---:|
| Combined included inventory | 18 | 5 | 13 | **64.95%** (1 − C(13,3)/C(18,3)) |

## All 18 included attempts

| # | Run / evaluation ID | Stages | Verdict | Reason | Eval | Live viewer |
|---|---|---|---|---|---|---|
| 1 | `bs3vx7tjzs9ihhnuyldiu725` | 6/6 | PASS (1) | Exact cart; all six strict checks PASS | [open](https://app.primeintellect.ai/dashboard/evaluations/bs3vx7tjzs9ihhnuyldiu725) | [expired](https://t-2-f742c42e20a21de3.tunnel.pinfra.io) |
| 2 | `dihf43ibedjbezh1jvjreuli` | 0/6 | INVALID (0) | Task app not visible mid-episode (infrastructure) | [open](https://app.primeintellect.ai/dashboard/evaluations/dihf43ibedjbezh1jvjreuli) | [expired](https://t-1-2f0b73f01e8d8320.tunnel.pinfra.io) |
| 3 | `tq9ha63oz0w9yuxtymect888` | 6/6 | FAIL (-1) | action_audit: two rejected focus taps; cart exact | [open](https://app.primeintellect.ai/dashboard/evaluations/tq9ha63oz0w9yuxtymect888) | [expired](https://t-2-29d5df0e0a3c9d68.tunnel.pinfra.io) |
| 4 | `bwrsq3jdu1mewwkpqymun7ub` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/bwrsq3jdu1mewwkpqymun7ub) | [expired](https://t-1-291b2d7b71966899.tunnel.pinfra.io) |
| 5 | `gr91nwweuqx4as244x168szl` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/gr91nwweuqx4as244x168szl) | [expired](https://t-1-a1ca05ded27f713c.tunnel.pinfra.io) |
| 6 | `fb5xisijf9aijeks9g0bwqt4` | 6/6 | PASS (1) | Exact cart; all checks PASS (13 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/fb5xisijf9aijeks9g0bwqt4) | [expired](https://t-0-fc7cd7ae8cf882a4.tunnel.pinfra.io) |
| 7 | `xnkxqfc8krobsqbua31ryp0z` | 6/6 | PASS (1) | Exact cart; all checks PASS (11 requests) | [open](https://app.primeintellect.ai/dashboard/evaluations/xnkxqfc8krobsqbua31ryp0z) | [expired](https://t-2-15c9ed937efab2c9.tunnel.pinfra.io) |
| 8 | `vstg6956ua06he82f98k76as` | 6/6 | INVALID (0) | action_audit: ADB_TRACE_UNASSESSABLE; cart exact | [open](https://app.primeintellect.ai/dashboard/evaluations/vstg6956ua06he82f98k76as) | [expired](https://t-0-778ca0629bce25ce.tunnel.pinfra.io) |
| 9 | `n4g39di2z9gbd4e9y310hb7a` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/n4g39di2z9gbd4e9y310hb7a) | Not exposed (local run) |
| 10 | `alaphi5mjth2j0yw2zgigo9r` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/alaphi5mjth2j0yw2zgigo9r) | Not exposed (local run) |
| 11 | `eyscer335lec20ljnqu1ko7e` | 0/6 | INVALID (0) | Pipeline error: ADB text-input command timed out | [open](https://app.primeintellect.ai/dashboard/evaluations/eyscer335lec20ljnqu1ko7e) | Not exposed (local run) |
| 12 | `mw6psxe3t9gx85u3s4rgkw4c` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/mw6psxe3t9gx85u3s4rgkw4c) | Not exposed (local run) |
| 13 | `hpw2xq3fphzlde6vwhjbyn2s` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/hpw2xq3fphzlde6vwhjbyn2s) | Not exposed (local run) |
| 14 | `vs737evcs6ns0znwjgfrbpv8` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/vs737evcs6ns0znwjgfrbpv8) | Not exposed (local run) |
| 15 | `xj28axy0df2g5nm87xl0csyz` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/xj28axy0df2g5nm87xl0csyz) | Hosted viewer expired |
| 16 | `k3sm3z2xo42w3ysbof59a6rn` | 6/6 | FAIL (-1) | ITEM.DC001, ITEM.DC002 and ITEM.DC003 optimization policies FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/k3sm3z2xo42w3ysbof59a6rn) | Hosted viewer expired |
| 17 | `nj22ajz4yjurhy3pbb8efbth` | 6/6 | FAIL (-1) | action_audit REQUIRED_CLAIM_UNMET; ITEM.DC001, ITEM.DC002 and ITEM.DC003 FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/nj22ajz4yjurhy3pbb8efbth) | Hosted viewer expired |
| 18 | `gigy0i7oy3o7xi41nqlvqn6x` | 6/6 | FAIL (-1) | action_audit REQUIRED_CLAIM_UNMET; ITEM.DC001, ITEM.DC002 and ITEM.DC003 FAIL | [open](https://app.primeintellect.ai/dashboard/evaluations/gigy0i7oy3o7xi41nqlvqn6x) | Hosted viewer expired |

Attempts 1–8 are public copies of the first eight original hosted-source evaluations. Attempts 9–14 are public copies of six sequential local software-emulated evaluations. Attempt 15 is a verified public copy of hosted smoke evaluation `pfcwnwz0whzbaeje3oiee29r`. Attempts 16–18 are verified public copies of included rollouts 1, 2 and 4 from hosted evaluation `g1n2vai2y27a02q7hd7vn17f`. INVALID outcomes remain INVALID and are never relabeled as model failures.

Excluded from the n=18 calculation at the user’s request: hosted rollout 3, [`st6fb03vzn4720vx4xr2f9ju`](https://app.primeintellect.ai/dashboard/evaluations/st6fb03vzn4720vx4xr2f9ju), PASS (1); and hosted rollout 5, [`on5z3bwthvjabf2t3wxc56uf`](https://app.primeintellect.ai/dashboard/evaluations/on5z3bwthvjabf2t3wxc56uf), PASS (1). Both remain valid public evaluations; this is an outcome-based reporting exclusion, not an INVALID classification.

## Evidence recorded per included evaluation

Each evaluation has a GitHub-hosted neutral evidence ZIP arranged by evaluation ID. Each archive contains only the verifier receipt, screenshots, and either the captured MP4 or its retained video reference. Credentials remain private.

| # | Verdict | GitHub evidence ZIP (SHA-256) | Eval |
|---|---|---|---|
| 1 | PASS | [evidence.zip (`c01394138a089187406ad79bcde5bb7d78dfc839238851d668b58ead84f2c12f`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/bs3vx7tjzs9ihhnuyldiu725/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/bs3vx7tjzs9ihhnuyldiu725) |
| 2 | INVALID | [evidence.zip (`f3821fa2f2408abe58d09bebf43ceac54d0f56ff02e362ba93070596b129c823`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/dihf43ibedjbezh1jvjreuli/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/dihf43ibedjbezh1jvjreuli) |
| 3 | FAIL | [evidence.zip (`5fcc38997710f8586e59fe88e580080fe65379b2e9ba22f4954a79d3b3d12f31`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/tq9ha63oz0w9yuxtymect888/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/tq9ha63oz0w9yuxtymect888) |
| 4 | PASS | [evidence.zip (`b95002d4d42c041cd96669d3164630d895470fc61d13898aa58183d929ca38e8`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/bwrsq3jdu1mewwkpqymun7ub/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/bwrsq3jdu1mewwkpqymun7ub) |
| 5 | PASS | [evidence.zip (`a4b7c7867ea318bf805fcc06bb25099b83317a734dfb3f22f8168f8952c8977b`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/gr91nwweuqx4as244x168szl/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/gr91nwweuqx4as244x168szl) |
| 6 | PASS | [evidence.zip (`1ae15c4ec07747aa7f64bc67956968570ded943496b130f083a929cded5785bf`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/fb5xisijf9aijeks9g0bwqt4/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/fb5xisijf9aijeks9g0bwqt4) |
| 7 | PASS | [evidence.zip (`6f50a8f3d193f07c558b4e015102e0142d5d441b0199110abe4751becfa38721`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/xnkxqfc8krobsqbua31ryp0z/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/xnkxqfc8krobsqbua31ryp0z) |
| 8 | INVALID | [evidence.zip (`2139ed6450ee3d99381dafd34c49081f2a91c7ef8846f8ff29927ed241463cc7`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/vstg6956ua06he82f98k76as/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/vstg6956ua06he82f98k76as) |
| 9 | FAIL | [evidence.zip (`a3eb2d4c2ec5d31d66b549db87c42854e8ccfedb2ff143e9ec35d3c7ed86104f`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/n4g39di2z9gbd4e9y310hb7a/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/n4g39di2z9gbd4e9y310hb7a) |
| 10 | FAIL | [evidence.zip (`1cc8b99cdb10eb65c7eb95d4261c58f02fdc84fd1014b4597fb15eb58128f822`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/alaphi5mjth2j0yw2zgigo9r/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/alaphi5mjth2j0yw2zgigo9r) |
| 11 | INVALID | [evidence.zip (`1f6acbcd296bca66357cf0714918f6c474d3d7480f306fb961a4cfbdcf8a5fe8`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/eyscer335lec20ljnqu1ko7e/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/eyscer335lec20ljnqu1ko7e) |
| 12 | FAIL | [evidence.zip (`bc71d54e023c0d0032c36af943f917abec6608c3cc7fa0234d59c12a313ce679`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/mw6psxe3t9gx85u3s4rgkw4c/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/mw6psxe3t9gx85u3s4rgkw4c) |
| 13 | FAIL | [evidence.zip (`35783857ea0bbd4f37ba47bee9b863c831c4cbb9c1ea3a48d801d4d28533cadd`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/hpw2xq3fphzlde6vwhjbyn2s/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/hpw2xq3fphzlde6vwhjbyn2s) |
| 14 | FAIL | [evidence.zip (`ffbe2761a5358e8e72a0f2bc631a278a52b3ccce01251007dc539b800c391d0f`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/vs737evcs6ns0znwjgfrbpv8/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/vs737evcs6ns0znwjgfrbpv8) |
| 15 | FAIL | [evidence.zip (`5b902df0235c194dc5dea49154da049b4e51437525205fea1d42547f8e30b8fd`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/xj28axy0df2g5nm87xl0csyz/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/xj28axy0df2g5nm87xl0csyz) |
| 16 | FAIL | [evidence.zip (`4faa35bdbfb2997ffee37ccca52a5abfd96a064222e562d9ad2e81dfecf73b9b`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/k3sm3z2xo42w3ysbof59a6rn/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/k3sm3z2xo42w3ysbof59a6rn) |
| 17 | FAIL | [evidence.zip (`440e8bfc1f52d2bb7edc4bf3d5bfc52ff54a1ae1b51565a98b835bdd72ec9a58`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/nj22ajz4yjurhy3pbb8efbth/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/nj22ajz4yjurhy3pbb8efbth) |
| 18 | FAIL | [evidence.zip (`3df23fd98a258b8dff0c48f05daed90caf5f8540feca068d118f8b1c7082e8c2`)](https://github.com/Teraformer09/browser-is-all-you-need/blob/Android-ADK-Verifiers/eval/evidence/gigy0i7oy3o7xi41nqlvqn6x/evidence.zip?raw=1) | [open](https://app.primeintellect.ai/dashboard/evaluations/gigy0i7oy3o7xi41nqlvqn6x) |

### What each evidence.zip contains

| File / path | Kind | Details |
|---|---|---|
| `verifier_receipt.json` | Verifier receipt | Final reward, verdict, strict checks, policy scores, optimizer results, reason codes and evidence references. |
| `screenshots/NNN.png` | Per-step screenshots | Recorded Android UI screenshots in evaluation order. |
| `video/screen-recording.mp4` or `video/reference.json` | Video evidence | Captured Android recording when the MP4 was retained locally; otherwise the immutable Prime artifact reference and SHA-256. |

The strongest directly verified result is that the 18 included public samples contain 5 PASS, 10 FAIL and 3 INVALID outcomes. The main boundary is that attempts 1–8, 9–14, 15 and 16–18 use different evaluation configurations, so only their separate group results should be used for controlled comparisons.
