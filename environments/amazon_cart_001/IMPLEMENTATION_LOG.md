# Source-layout update — 2026-09-07

The task is now split into named parts: the Android app stores the simulated business state; the harness performs UI actions; the verification package reads evidence and scores policies; the Prime integration handles environment loading and explicit result uploads. Equivalent roles in the new payment and cart packages use the same filenames.

This cleanup did not run a new model evaluation or change historical screenshots, model labels, rewards or artifact hashes. AppState is a source-class rename, not a changed transaction/cart behavior. After the workspace restriction was clarified, remaining edits, caches and temporary outputs were moved under /data/Tirtha; existing SDK/JDK/Gradle installations are only tool inputs, and no further shared Gradle-cache write was requested.

| File or component | Exact change and logic | Why | Validation boundary |
|---|---|---|---|
| `harness/actions.py`, `acceptance.py`, `episode.py` | Separate JSON validation, tool execution and app acceptance. Keep explicit approval and device selection; do not repair model actions. | A successful ADB command is not a completed business action. | Offline malformed-action and no-execution guard tests. |
| `verification/generic/validity.py`, `generic/interaction.py`, `semantic.py`, `task_checks.py` | Group evidence-backed checks by readiness, mechanics, semantic selection and task outcome. | Policies and the code that proves them have explicit locations. | Every policy has five distinct registered functions; unavailable channels produce INVALID. |
| `verification/registry.py`, `scoring.py`, `specs/policies.json`, `scoring.json` | Validate fourteen policy IDs and five verifier IDs each. Preserve support = 0.5 + 0.1 × PASS count, threshold >= 0.7, all-INVALID override and signed episode precedence. Broken registry returns a reasoned INVALID scorecard. | No new weights and no averaging of signed rewards. | Exhaustive 243 vote combinations and policy/failure tests. |
| `specs/task.json` | Keep one unchanged canonical task definition; remove the duplicate root task copy. | Harness and verifier cannot drift onto different task files. | Canonical-path, identity and wheel-resource tests. |
| `AppState.java`, `AppStateTest.java` | Rename the domain-state class and its test to the same filename in both apps; update all Java references. | Same responsibility, same name; Android namespaces remain distinct. | Both APKs and their JVM tests compiled successfully before the write-location restriction was clarified. |
| `pyproject.toml`, `__init__.py`, `integrations/prime_env.py` | Package the whole task implementation and JSON resources, with a lazy public loader and no automatic device launch. | Source checkout and installed wheel must have the same behavior. | Source distribution/wheel build and isolated loader checks. |
| `scripts/build_apk.sh`, `.gitignore` | Default Gradle caches and temp files to task-local artifacts; exclude generated builds, signing keys, credentials, caches and run artifacts from source commits. | Keep infrastructure output out of source history. | Source allowlist and credential-pattern audit before staging. |
| `verification/evidence_readers.py`, `task_checks.py`, `cli.py` | Add the 14×5 cart verifier layer and real model episode runner. Replay accepted operations using the app's fixed six-item catalog, then verify exact products, quantities, prices, distinct searches, totals and cart review. | The previous version had an exact-cart checker and a scripted UI runner only. | Offline positive/negative/invalid fixtures; no claim of a new live model pass. |
| `integrations/legacy_scripted.py`, `records.py` | Retain the original frozen scripted-result validation separately from the genuine model exporter. | Never relabel the previous DemoCart run as an LLM evaluation. | Original frozen evidence remains reproducible under its original rubric. |

## Earlier implementation history

# DemoCart — implementation and patch log

DemoCart is an offline, Amazon-style Android shopping demo. It uses a dark shopping header, yellow Material action buttons, search results, illustrated product cards and a separate cart. Products and prices are fictional; the app is not affiliated with Amazon, does not connect to Amazon, has no login or checkout, and cannot place an order.

This is a separate environment, amazon_cart_001, with Android package com.primeintellect.shoppingdemo. The payment and Uber apps, their files and their saved runs are unchanged. The requested milestone is the app and a locally demonstrated three-search/three-item cart workflow. A scripted UI validation is not a model evaluation or a Prime-hosted run.

## Patch 001 — shopping app and exact cart task

The fixed task is to search separately for Nimbus Wireless Headphones, Trail Steel Water Bottle and Metro Laptop Backpack. The final cart must contain exactly one of each and no extra products. Their fictional prices are INR 2,499.00, INR 699.00 and INR 1,799.00, giving INR 4,997.00. The catalog also has wired headphones, a sports bottle and a small daypack, so a similar-looking but different SKU does not satisfy the task.

| File or component | What changed and how the code works | Verification |
|---|---|---|
| app/shopping_android_app/app/build.gradle | New application ID; reused pinned Material 1.12.0, AppCompat 1.7.0, AGP 8.7.3, Gradle 8.9 and SDK 34 settings. Java language level remains 8 with the existing JDK 21 runner. | Final build and all 17 JVM tests passed; installed APK hash matched. |
| Catalog.java | Defines six immutable fictional product identities, descriptions and integer-paise prices. Search is case-insensitive and every query token must match a product's name, details or category. | Exact, broad, case/whitespace and no-result tests. |
| AppState.java | Keeps submitted search separate from editable search text, records each search/result set, and only permits adding a SKU from the current valid results. Cart quantities are 0–9; decrementing to zero/removing deletes the row. | Search preconditions, stale results, wrong SKU, duplicates, quantity limits and recovery tests. |
| AppState.restore | Replays stored accepted operations, then compares derived cart/history/counters against the saved state. Reopening does not run the task again or silently duplicate products. | Restore and tampered-state tests. |
| MainActivity.java | Builds native Material views with stable IDs. Typing updates the draft and disables old result actions; Search submits the query and dismisses the keyboard. Add buttons update the cart; cart rows expose plus/minus/remove and a subtotal. | Final live run passed; search and cart PNGs visually inspected after Patches 004–005. |
| res/values/styles.xml and ids.xml | Define the Amazon-inspired palette, compatible Material theme and explicit resource IDs for all six products and cart controls. | Compiled by Android resource merging. |
| res/drawable/product_*.xml | Three local vector illustrations for headphones, bottle and backpack. No borrowed product photos, image downloads or generated screenshots. | Inspect actual app screenshots. |
| StateStore.java | Stores one atomic shopping_state/snapshot JSON containing state plus ordered accepted/rejected app events. Distinct explicit episode IDs start fresh state. | Live/persisted-state consistency and restart checks. |
| VerifierStateProvider.java and AndroidManifest.xml | New read-only, DUMP-protected shopping provider; no Internet, account, payment, location or checkout permission. | Manifest/build inspection and provider capture. |
| amazon_cart_001/specs/task.json | The one task's desired SKUs, suggested queries, quantity one, prices, expected subtotal and cart-open requirement. Task answers are not hard-coded into the app's success logic. | Python task/schema/total validation. |
| amazon_cart_001/verifier.py | Checks trusted episode identity, exact cart SKUs/quantities/prices, correct line/subtotals/counters, three distinct search IDs tied to accepted adds, and visible-cart state. | Wrong/missing/extra items, bad quantities, stale/missing evidence and provenance tests. |
| amazon_cart_001/device.py | Reuses the tested explicit-serial ADB transport and freezes UI XML, original PNG, persisted state, live state and journal around each step. No model is called. | Stable before/after snapshot hashes and command receipts. |
| amazon_cart_001/run_demo.py | Runs only a declared scripted sequence through actual UI actions: type/search/add for each item, then open cart. It never writes cart state through the provider or edits preferences. | Final live run recorded 10 UI actions and 11 screenshots. |
| scripts/ | Separate build/install/start/demo helpers. Installation compares local and installed APK hashes. Emulator ports 5042/5582/5583/8570 are separate from the payment setup. | Device identity, APK hash and bounded teardown. |
| tests/ and Java AppStateTest.java | Automated checker and business-model regressions, separate from live UI demonstration. | 17 JVM tests and 16 Python tests passed; receipts below. |

Search progress is independent of adding: a matching recorded search completes its search stage; a current correct cart quantity completes its cart stage. The six stage flags are diagnostics, not an arbitrary weighted reward. Final PASS=1 requires all exact cart/provenance constraints; an assessable mismatch is FAIL=-1, and unavailable or inconsistent essential evidence is INVALID=0. The live demonstration is always labeled scripted-ui-validation, model_calls=0 and training_eligible=false.

This milestone uses a dedicated deterministic search/cart verifier. It does not claim to have ported the payment app's fourteen-policy/seventy-verifier voting layer, a model actor or Prime publication. Those integrations need a separate request and validation; no old ride/payment policy is silently reused for shopping.

## Change-log rule

Every later patch must update this file alongside its code. Record the observed problem, exact files/functions, before/after behavior, test/run IDs and remaining limitations. Preserve unsuccessful run artifacts and never relabel a scripted demonstration as a model evaluation.

## Patch 002 — exact numeric restoration checks

The first APK build and JVM suite completed successfully. Code review then found that AppState.equivalent compared Number values by longValue(), which could truncate a corrupt saved subtotal such as 0.5 to zero. It now compares BigDecimal values exactly. A new fractionalSavedTotalIsRejected regression ensures fractional tampering is rejected rather than silently normalized during restoration. No catalog price or legitimate cart operation changed. The original 16 Python verifier tests pass; the expanded Java suite and patched APK are rebuilt before the live demonstration.

Build warning retained: Java 21 warns that Java-8 source/target support is deprecated. This is the same compatible build choice as the payment demo; no server JDK, shared SDK or other project was modified. Wrapper and dependency versions remain pinned.

## Patch 003 — install waited for ADB, but Android was not booted

The patched APK and all 17 Java tests built successfully. The first install attempt reached ADB before Android's package service was available and returned: cmd: Can't find service: package. No task action ran and no app-state verifier failed. scripts/install_apk.sh now waits for sys.boot_completed=1 and a working pm path android response, with a 120-second deadline and individually bounded ADB probes, before installing. It still requires the explicitly selected emulator and still verifies the installed hash. This is an emulator-readiness fix, not an app/verifier workaround.

## Patch 004 — visible cart-control labels

Run 20260907T125259Z_b6d989bc passed all exact-cart checks after 10 scripted UI actions, but direct inspection of frames/010/screen.png revealed a presentation defect: Material's inherited horizontal padding left too little text space in the 46-dp quantity buttons, and Remove wrapped inside a 36-dp-high row. The task result remains a true exact-cart PASS; it did not establish that every control label rendered correctly.

MainActivity.button now sets explicit 12-dp horizontal padding, zero inherited minimum dimensions, one-line text and centered gravity. MainActivity.productCard gives the cart quantity buttons and control row 48-dp height, makes the quantity buttons 48-dp wide and keeps the Remove button 90-dp wide. This exposes the labels and provides larger cart touch targets without changing catalog, business-state logic, task requirements or reward logic. The earlier run is preserved; the patched APK must be rebuilt, reinstalled with a matching hash and demonstrated in a fresh scripted run before visual readiness is claimed.

## Patch 005 — search-input contrast

The cart-control fix passed in run 20260907T130031Z_05f44f2e, and its final PNG showed readable quantity/Remove labels. Inspection of its search-result screenshot, frames/002/screen.png, revealed a separate visual issue: the inherited EditText background prevented the intended white search surface from rendering, leaving dark query text on the navy header. Native targeting and search worked, but the contrast was poor.

MainActivity.buildUi now gives the TextInputLayout an explicit rounded white GradientDrawable background and clears the child EditText's inherited background so Material can own the field decoration. Text, hints, search semantics and resource IDs remain unchanged. This is a UI-only patch; task/verifier logic is unchanged. Both earlier scripted runs remain preserved. A rebuilt, hash-verified APK and fresh complete UI run will validate this final presentation fix.

## Final validation — 2026-09-07

The final patched app completed the requested task through actual ADB-driven UI input. Run `20260907T130453Z_2ca02a6e` searched separately for all three products, added one of each and opened the cart in 10 actor actions, taking 87.58 seconds. No model call, checkout, real purchase, Docker container or Prime upload was involved.

| Check | Direct result | Exact evidence |
|---|---|---|
| JVM business-model tests | 17 tests, zero failures/errors/skips. | `app/shopping_android_app/app/build/test-results/testDebugUnitTest/TEST-com.primeintellect.shoppingdemo.AppStateTest.xml` |
| Python task-verifier tests | 16 tests passed. | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` |
| Shell helpers | All four scripts passed `bash -n`. | `scripts/build_apk.sh`, `install_apk.sh`, `start_emulator.sh`, `run_demo.sh` |
| Installed binary | Local and installed SHA-256 match. | `artifacts/ui_demo/20260907T130453Z_2ca02a6e/installed_apk.json` |
| Exact cart | PASS = 1; 3 distinct products, quantity 1 each, total quantity 3, subtotal 499700 paise. | `artifacts/ui_demo/20260907T130453Z_2ca02a6e/verdict.json` and `final_state.json` |
| Progress | 6/6 diagnostic stages complete; cart-open condition also passes. | `artifacts/ui_demo/20260907T130453Z_2ca02a6e/progress_history.json` |
| Action evidence | 10 accepted actor actions; 11 stable initial/after-action frames. | `trajectory.jsonl`, `adb_actions.jsonl`, `frames/000` through `frames/010` |
| Screenshots | 11 original PNGs; final search/cart screens visibly readable after layout fixes. | [All screenshots](artifacts/ui_demo/20260907T130453Z_2ca02a6e/SCREENSHOTS.md) |
| Artifact integrity | All 96 files listed in the run manifest matched their recorded SHA-256 hashes. | `artifacts/restoration/20260907T130701Z_8144962d/receipt.json` |
| Restart restoration | Same episode, cart, quantities, subtotal, search/add histories, operations and revision restored; all 10 equality checks passed. | `artifacts/restoration/20260907T130701Z_8144962d/receipt.json` and its captured frame |
| Earlier attempts | Both earlier scripted runs are retained, including their visual defects. | `20260907T125259Z_b6d989bc` and `20260907T130031Z_05f44f2e` |

Final APK: `app/shopping_android_app/app/build/outputs/apk/debug/app-debug.apk`.

Final APK SHA-256: `e93d1333e773be95a3dc4971c86109cecb505c114e7c30bf1b621c602a85bc0d`.

The run's manifest proves captured-file consistency, not independent correctness of every evidence source. Its exact-state verifier and visual inspection are distinct checks: a cart can be correct while a control label is clipped, which is why Patches 004 and 005 were needed. Validation was on the dedicated API-33 Pixel-6 emulator; other screen sizes, font scales, production security, model behavior and Prime deployment have not been established.

The describe-systems skill guided this evidence-led log: observed UI failures, business-state results and unverified deployment claims are kept separate. Future code changes must continue updating this document with their tests and run receipts.

## Task-owned runtime cleanup

After the final screenshot and restart receipts were saved, CartDemo_001 on emulator-5582 was stopped. Its private ADB server on port 5042 was also stopped. Android avdmanager removed only the validated generated AVD at /tmp/cart-demo.jJJ0kl/device, then the empty /tmp/cart-demo.jJJ0kl directory was removed. Approximately 1.2 GB of recreatable emulator data was reclaimed; the temporary device's live cart is no longer running. The installed app and cart can be recreated by the README workflow, while all original screenshots, JSON evidence, source and the final APK remain saved. Ports 5042, 5582, 5583 and 8570 were checked and are no longer listening. No Docker container/image was created or removed for this task, and shared SDKs and other project resources were not deleted.

## Patch 006 — source-free Prime result upload

The user requested uploading this existing DemoCart result to Prime. This is not authorization to silently relabel the scripted actor as an LLM, launch another run or publish the source package. `amazon_cart_001/upload_results.py` therefore imports only the recorded result under the authenticated personal `terrano09` account. The original APK, task, verifier and frozen run are unchanged.

The new exporter checks all 96 original artifact hashes, task-definition identity, the recomputed final verdict, ordered action receipts, stable same-episode frames and all eleven original PNGs before any remote write. It exports only allowlisted result JSON/XML/action logs and screenshots, rejects credential-like strings and payloads of 25 MiB or larger, and labels both the evaluation and reconstructed conversation view as scripted UI validation with zero model calls and no training eligibility. The transcript is a display reconstruction of recorded actions, not a claim about an original model prompt.

The upload uses a private metadata-only environment record named `terrano09/amazon-cart-001`; it sends no wheel, source archive, APK or Docker image, and requests no hosted compute. A new local receipt directory, `artifacts/prime_upload/20260907T130453Z_2ca02a6e/`, keeps upload receipts separate from the frozen original run. The receipt pins the payload hash and supports resuming without intentionally duplicating a sample. After upload, the script retrieves the sample and compares ordered screenshot hashes/references, all exported log contents, the reward and the scripted/no-model labeling. Stored artifact consistency does not establish browser rendering; that field remains explicitly unverified.

| Check or issue | Observation | Implementation or result |
|---|---|---|
| Account context | Prime whoami returned terrano09 and no active team. | Upload checks this again before remote writes and restricts the API host to api.primeintellect.ai. |
| Existing DemoCart records | Personal-account evaluation list returned total=0 for amazon-cart-001. | This will create a new result record, not overwrite the payment evaluation. |
| SDK slug lookup caveat | A preflight lookup using team_slug=terrano09 returned HTTP 403: not a member of this team. | terrano09 is a personal owner, not the named team. The uploader uses the CLI-supported explicit owner_slug field for metadata resolution, then the returned environment ID. No team permission is bypassed or changed. |
| Local export dry run | PASS; 10 actions, 11 PNGs, 86 text logs; 10,880,443 serialized bytes. | Under the full-sample size cap; no source files are included. |
| Regression tests | 15 new upload checks plus 16 existing task-verifier tests passed (31 Python tests). | `tests/test_upload_results.py` covers labels, counts, path escapes, changed reward/logs, missing/duplicate images and duplicate remote samples. |
| API contract | Checked installed Prime CLI 0.6.21 and the official create/push documentation. | [Create evaluation](https://docs.primeintellect.ai/api-reference/evals/create-evaluation), [push samples](https://docs.primeintellect.ai/api-reference/evals/push-samples). |

The previous payment uploader's real-model-only guard remains unchanged. DemoCart uses a separately named scripted exporter; this does not relax an existing model benchmark's policy.

## Patch 007 — personal namespace creation, not collaborator lookup

The first upload attempt for `20260907T130453Z_2ca02a6e` stopped at metadata registration with HTTP 400: Environment 'terrano09/amazon-cart-001' not found. Collaborators cannot create new environments. No evaluation or sample was created by that attempt. Its diagnostic receipt is `artifacts/prime_upload/20260907T130453Z_2ca02a6e/registration_attempt_1.json`.

The server treats an explicit `owner_slug` as an existing-environment collaborator route, even when the text matches the authenticated personal slug. `upload_results.upload` now omits that field and follows the installed EvalsClient's normal get-or-create behavior in the current personal account, sending only the name and PRIVATE visibility. The prior whoami=terrano09/no-team/API-host checks still execute first. No credentials, roles, permissions, owner selection, task result or source-publication scope changed. This corrects the request shape; it does not bypass a team authorization check.

## Prime result completed — 2026-09-07

The existing scripted UI result is now saved under the `terrano09` personal account at [this Prime evaluation](https://app.primeintellect.ai/dashboard/evaluations/kl9bsyib7fjf81699n0d4ik6). Prime reported COMPLETED after initially processing the accepted sample. No new app run, model inference, Docker process or Android emulator was started during this upload.

| Uploaded component | Verified result | Receipt |
|---|---|---|
| Evaluation | ID `kl9bsyib7fjf81699n0d4ik6`; COMPLETED; total_samples=1; avg_score=1.0. | `artifacts/prime_upload/20260907T130453Z_2ca02a6e/prime_upload.json` |
| Environment association | ID `ct6a6yjs0nvjkzexo3s57hqf`; newly created metadata record owned by user terrano09, name amazon-cart-001. | `prime_upload.json#/environment_registration` |
| Actor identity | Model label `scripted-ui-validation (no model)`; model_calls=0; is_hosted=false. | `prime_upload.json#/evaluation`, returned sample info |
| Screenshots | All 11 ordered PNG references/hashes match the original initial/after-action screenshots. | `prime_upload.json#/verification` |
| Text logs | All 86 exported JSON/XML/action logs match the saved original contents. | `prime_upload.json#/verification` and `prime_samples.json` |
| Task result | Reward 1, 6/6 diagnostic stages, exactly three cart items, ten recorded UI actions. | Returned sample and evaluation metrics |
| Visibility | is_public=false and show_on_leaderboard=false. | Evaluation receipt |
| Training and hosting | training_eligible=false; no model/hosted-compute or source-package publication claim. | Sample info and metadata |
| Browser rendering | Not independently checked in an authenticated browser. | browser_rendering_verified=false; API evidence verification is not a rendering test. |

The final documentation adds the dashboard URL and exporter command to README.md. The original frozen run directory and APK were not changed. The evidence-led describe-systems reporting keeps the imported scripted result distinct from any future model benchmark, while preserving the real PASS and all recorded diagnostic evidence.
