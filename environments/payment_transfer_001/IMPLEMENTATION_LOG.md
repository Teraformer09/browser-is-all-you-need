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
| `verification/evidence_readers.py`, `task_checks.py` | Relocate the existing payment predicates and evidence readers without changing their policy claims. | Preserve recipient, amount, account, note, reviewed revision and single simulated receipt semantics. | Existing regression suite remains green after relocation. |

## Earlier implementation history

# Material payment demo — implementation and patch log

This project builds a small simulated payment app using Material Components for Android. The library supplies buttons, input fields, cards and themes, not a finished payment app. Our Java code supplies the payment workflow and its recorded state; the Python evidence tools inspect that state. No real bank, payment gateway or money movement is involved.

This is a separate environment named payment_transfer_001. Uber-031 and its evidence are untouched. Patches 001–008 document the original UI milestone. From Patch 009 onward, the model runner, fourteen-policy/seventy-verifier layer and Prime integration are being added. Historical prototype limitations below describe that earlier milestone; the latest patch and run receipts state what has actually been validated.

## Design and build choice

We use the library as a Gradle dependency rather than cloning its entire repository. Material 1.12.0 and AppCompat 1.7.0 are pinned for this Java/Views demo. Gradle 8.9 and Android Gradle Plugin 8.7.3 coordinate resource merging, Java compilation, dependency packaging and debug signing. Both compile SDK and target SDK are 34, with minimum SDK 23; there is no second conflicting manual SDK configuration.

The Views library is in maintenance mode, not removed or unusable. Google directs future feature development toward Compose. We retain Views here to match the existing Java approach, and do not describe it as the newest UI stack.

Sources: [repository and maintenance notice](https://github.com/material-components/material-components-android), [versioned setup guide](https://github.com/material-components/material-components-android/blob/1.12.0/docs/getting-started.md), [pinned release](https://github.com/material-components/material-components-android/releases/tag/1.12.0).

## Patch 001 — separate Material payment implementation (2026-09-07)

Initial status: implementation started here. The later patch entries preserve failures and fixes; the final validation section records the current working result.

| File / component | Exact logic and reason | Validation |
|---|---|---|
| app/build.gradle | Pin Material/AppCompat, set separate package and SDK 34, map existing-style src/res directories, add JVM tests. | Built and installed; see final validation. |
| MainActivity.java and layout XML | Replace the ride UI with mock recipient, amount, account, note, review and confirmation controls; stable IDs identify each control. | 14 Android UI assertions pass after Patch 007. |
| AppState.java | Separate editable draft from immutable reviewed/committed values; represent money as integer paise; reject stale reviews and make repeated confirmation idempotent. | 13 JVM transaction tests pass. |
| StateStore.java and VerifierStateProvider.java | Persist JSON state and action receipts; expose read-only same-episode snapshots protected by DUMP permission. | Live provider capture and process-restart restoration pass. |
| scripts/build_apk.sh | Use Gradle unit-test and APK tasks, not direct javac/aapt assembly. Gradle includes library resources/dependencies. | Public build/install/test scripts exercised successfully after Patch 006. |
| scripts/install_apk.sh | Require an explicit device and compare local/installed APK hashes; never uninstall another app to repair signing. | Installed only on the temporary test AVD; APK hashes match. |
| Python evidence collector and verifier | Read payment app evidence and inspect committed transaction fields; no actor, model call or remote upload. | 15 offline Python tests pass; live record capture passes. |

## Patch-log maintenance rule

Every later patch must update this file in the same change: record the observed issue, affected file/function, exact behavior before and after, test command/result, and anything still unverified. Never replace a failed run with a claimed success. Keep simulator tests, model evaluations and Prime publication separate.

## Patch 002 — explicit build JDK (2026-09-07)

The first Gradle invocation failed before compilation: the server's default Java was 11, but AGP 8.7.3 requires Java 17 or newer. This was a build-tool mismatch, not a payment logic failure. The build script now requires JAVA_HOME and rejects older JDKs with an explicit error before running Gradle. Validation uses the already installed Java 21 for this command only; the server-wide default was not changed.

The initial Python outcome-checker suite passed all 11 tests. These are synthetic offline checks, not model evaluations or proof of live UI behavior.

## Patch 003 — reproducible wrapper and UI contract test (2026-09-07)

The Java-21 retry built the Material APK successfully and passed 13 JVM transaction tests. The compiler warned that Java 8 source/target support is obsolete on Java 21. The app's compileOptions now use Java 17, which the selected Gradle/AGP toolchain supports, instead of hiding that warning.

The generated Gradle 8.9 wrapper is included. Its distribution checksum is pinned to the official value (d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab); this detects a changed Gradle download. The UI instrumentation test checks disabled prerequisites, review invalidation, confirmation, receipt visibility and repeat-confirmation behavior. It is a deterministic app smoke test, not a model evaluation. Live results are pending.

## Patch 004 — host JDK is missing jlink (2026-09-07)

The Java-17 language-level attempt failed because the installed Java 21 directory has no bin/jlink; AGP's Android JDK-image transform could not run. Rather than change the shared server JDK or hide the failure, compileOptions returns to Java 8 language/bytecode, which already built this app successfully. Gradle still runs on Java 21. The known Java-8 deprecation warning remains visible. No payment behavior or verifier threshold changed. A future move to Java-17 language features requires a complete JDK and a fresh build test.

## Patch 005 — safe UI-test transport and capture checks (2026-09-07)

The emulator initially advertised unauthenticated gRPC. That owned test process was stopped before app testing and restarted with -grpc-use-jwt; the replacement binds gRPC to 127.0.0.1 and requires JWT authentication. It uses an isolated AVD, ports 5580/5581 and a private ADB server on 5041; no existing emulator is reused.

scripts/test_ui.sh requires an explicit UI-test approval flag and device serial, installs only the separately named demo/test APKs, and fails unless the instrumentation output reports all 12 assertions passed. The capture collector reads provider state before and after the UI/PNG capture; changes during capture, wrong-app UI or a bad PNG produce INVALID, not an agent failure. Four mocked collector tests cover these paths. The outcome checker also rejects boolean schema versions and unusable task parameter types.

## Patch 006 — build preflight parser (2026-09-07)

Running the public test_ui.sh entry point exposed an over-escaped regular expression in build_apk.sh: it incorrectly rejected Java 21 even though direct Gradle builds worked. The parser now reads Java's java.specification.version property with awk instead of parsing a version banner. An explicit Gradle-version check also rejects a GRADLE_BIN override that is not 8.9. This changes only build preflight, not application or scoring logic.

## Patch 007 — visible selected values and receipt (2026-09-07)

The first live UI test passed 12 assertions, and an actual restart/capture reproduced a completed transfer. Visual inspection of its PNG showed that disabled recipient/account buttons did not clearly distinguish the final selection, and the receipt was below the fold. MainActivity.render now puts the actual selected recipient and account in readable section labels, and scrolls to the receipt after completion/restoration. These labels are derived from model state, not the task's expected answers. The XML adds stable IDs for those labels and the ScrollView. Two UI assertions check the labels; test_ui.sh now requires 14 assertions. The earlier screenshot remains a historical artifact.

## Patch 008 — keep inspection evidence out of training (2026-09-07)

The standalone record checker reports whether a payment record matches the requested outcome; that is not proof of an agent rollout or the full policy contract. capture_evidence.py now explicitly marks all captured results capture_only=true and training_eligible=false, even when the record check passes. Its manifest includes the verifier and collector source hashes for provenance. Earlier captures are retained as historical smoke-test artifacts and must not be treated as training examples. No reward predicate or app logic changed.

## What changed inside the files, in plain language

### The screens: MainActivity.java, activity_payment.xml and styles.xml

The earlier ride app built its widgets directly in Java. This new app uses res/layout/activity_payment.xml to describe the payment form and MainActivity extends AppCompatActivity to inflate it. The XML uses MaterialButton, MaterialButtonToggleGroup, TextInputLayout, TextInputEditText, MaterialCardView and LinearProgressIndicator. styles.xml inherits Theme.Material3.Light.NoActionBar and sets a teal/light theme. Control IDs are declared with @+id in the layout itself; a separate ids.xml is not needed.

MainActivity connects each control to the model: recipient buttons call recipient(...), account buttons call account(...), and text watchers call amount(...) or note(...). act(...) catches rejected operations and displays their actual reason. render(...) derives enabled/hidden controls from the actual state: Review needs a valid draft; Confirm appears only for the current reviewed revision; completed transfers cannot be edited. The section labels show the actual selected recipient/account even when the buttons are disabled. The completed view scrolls to its receipt. It does not read the task's expected answer to invent a successful display.

### The payment rules: AppState.java

AppState is a plain Java class so it can be tested without Android. The app offers two mock recipients and two mock accounts, not real contact/bank access. Amount text is converted through BigDecimal into integer paise: INR 500.00 becomes 50000. The app rejects zero, negative values, more than two decimals and amounts above INR 1,000,000.00. Notes are limited to 80 characters; an empty note is allowed by the generic app, but this specific task requires Lunch.

Each changed draft increments revision and clears reviewedRevision. review() validates the draft and records the current revision. confirm() requires that reviewedRevision still equals revision, then creates one immutable transaction containing the episode, recipient, account, amount, currency, note and a receipt ID. A second confirm() returns that same transaction. After commitment, setters reject edits. restore(...) checks the persisted draft and receipt for consistency and restores the same transaction rather than creating another.

The central guard is:

```java
if (transaction != null) return new LinkedHashMap<>(transaction);
if (reviewedRevision != revision)
    throw new IllegalStateException("Review the current details before confirming");
```

That is an idempotent simulated confirmation, not a network payment, bank transfer or real financial ledger.

### Persistence and evidence: StateStore.java and VerifierStateProvider.java

StateStore saves one JSON value named snapshot in payment_state SharedPreferences. It contains the draft, transaction list and ordered action receipts together, using synchronous commit(). Rejected actions record accepted=false and an error without inventing a completed transfer. The initial empty state is also recorded. Reopening without a new episode ID restores the existing state; supplying a different explicit episode ID starts a separate test state. Corrupt state is reported as unavailable instead of silently converted into a successful reset.

VerifierStateProvider exposes content://com.primeintellect.paymentdemo.verifier/state. It reads the live model on the UI thread, with a two-second timeout. The manifest protects this provider with android.permission.DUMP. Insert, update and delete are rejected. Persistence failures make the live evidence unavailable and disable further app interactions. The provider and persisted state share app logic; they are not automatically independent proofs.

### App identity and build files

AndroidManifest.xml declares the separate package's activity/provider, the Payment Demo label and Material theme. The app declares no Internet, contacts, SMS, location or banking permission. The merged APK adds only AndroidX's app-specific dynamic-receiver permission. The payment package is com.primeintellect.paymentdemo, so installing it does not replace com.primeintellect.dummyrl.

settings.gradle names the project PaymentDemo, includes :app and enables Google/Maven Central repositories. The root build.gradle pins AGP 8.7.3 and configures the Gradle 8.9 wrapper checksum. app/build.gradle pins Material 1.12.0, AppCompat 1.7.0 and JUnit 4.13.2, uses compile/target SDK 34 and min SDK 23, maps the manifest/src/res directories, and registers the separate instrumentation runner. gradle.properties enables AndroidX and limits workers/memory. The generated gradlew, gradlew.bat and gradle/wrapper files make the build launcher portable. Top-level versions and the Gradle distribution are pinned; a full transitive dependency lockfile has not been added.

### Build/install/test scripts

build_apk.sh requires explicit SDK/JDK paths, checks JDK >=17 and Gradle 8.9, then runs testDebugUnitTest and assembleDebug. It prints the APK path/hash and never launches Android. Unlike the old direct aapt/javac script, Gradle packages Material's transitive dependencies and merged resources.

install_apk.sh calls that builder, requires an explicit ADB_SERIAL, installs with adb install -r, reads the installed package path and compares SHA256 hashes. It does not silently uninstall an app to work around signing problems. test_ui.sh additionally requires ALLOW_PAYMENT_UI_TEST=1, builds/installs the separate instrumentation APK and checks for the exact PASS: 14 payment UI assertions marker. Each test invocation gets a unique artifacts/ui_test.* log directory.

### Task and Python evidence tools

payment_transfer_001/specs/task.json declares the one example: simulated INR 500.00 to Alex, from account_1234, with note Lunch. The JSON is a small standalone inspection specification, not the legacy ride YAML factory. Its max_steps=16 is a proposed future actor budget; the read-only collector does not implement or enforce an actor loop.

payment_transfer_001/verifier.py checks the expected draft/committed fields, matching episode and review revision, receipt identity, simulated/completed flags and exactly one recorded transaction. Missing/unreadable essential state returns INVALID=0; an assessable wrong or absent transaction returns FAIL=-1; a matching committed transaction returns PASS=1. A success label or correct draft alone cannot pass. Its policy_layer is explicitly not_14x5: this is an initial record checker, not the existing seventy-verifier framework.

capture_evidence.py invokes only inspection commands on an explicitly selected device. It reads the protected provider before and after collecting UI XML and an original PNG, checks that the app/state stayed consistent, saves the evidence and hashes, then runs the record checker. Capture failures produce INVALID evidence. Captures are explicitly capture_only=true and training_eligible=false; they are not model rollouts. This script does not start an app, type, tap, confirm, call an LLM or upload to Prime.

### Tests and scope

AppStateTest.java exercises the pure transaction rules, including money precision, missing prerequisites, stale review, all editable fields, duplicate confirmation, immutability, restoration and corrupted state. PaymentUiTest.java runs in a separate instrumentation APK and exercises actual Material widgets. tests/test_verifier.py checks outcome mismatches, missing evidence, wrong episode, duplicate records and unsupported values. tests/test_capture.py mocks collection failure modes; it does not prove real UI rendering by itself.

The UI smoke test deliberately attempts premature confirmation to test rejection and recovery. Its final record can pass the record checker, but that does not make it a PASS under a future strict no-invalid-action policy. Do not upload this smoke trace as a successful model benchmark or use it for training.

## Current file tree

```text
payment_transfer_001/
├── .gitignore
├── README.md
├── IMPLEMENTATION_LOG.md
├── app/dummy_android_app/
│   ├── AndroidManifest.xml
│   ├── build.gradle
│   ├── settings.gradle
│   ├── gradle.properties
│   ├── gradlew / gradlew.bat
│   ├── gradle/wrapper/
│   │   ├── gradle-wrapper.jar
│   │   └── gradle-wrapper.properties
│   ├── res/layout/activity_payment.xml
│   ├── res/values/styles.xml
│   ├── src/com/primeintellect/paymentdemo/
│   │   ├── MainActivity.java
│   │   ├── AppState.java
│   │   ├── StateStore.java
│   │   └── VerifierStateProvider.java
│   └── app/
│       ├── build.gradle
│       ├── src/test/java/com/primeintellect/paymentdemo/AppStateTest.java
│       ├── src/androidTest/java/com/primeintellect/paymentdemo/PaymentUiTest.java
│       └── build/                         # Generated APK/test output, ignored
├── payment_transfer_001/specs/task.json
├── payment_transfer_001/
│   ├── __init__.py
│   └── verifier.py
├── scripts/
│   ├── build_apk.sh
│   ├── install_apk.sh
│   ├── test_ui.sh
│   └── capture_evidence.py
├── tests/
│   ├── test_verifier.py
│   └── test_capture.py
└── artifacts/                             # Original smoke logs/PNGs, ignored
```

## Final validation for this milestone (2026-09-07)

| Check | Actual result | Evidence / boundary |
|---|---|---|
| APK build | Successful using the public build/install/test scripts. | app/dummy_android_app/app/build/outputs/apk/debug/app-debug.apk |
| Installed APK identity | Matches the built APK: 6db0d97f03e6ef35c4e1443eabbaa68d17d54f9439ea58fc695c7d0d6eac8eb8. | Separate payment package on the temporary API-33 emulator. |
| JVM transaction tests | 13 passed, zero failures/errors. | app/dummy_android_app/app/build/test-results/testDebugUnitTest/ |
| Python tests | 15 passed. | python3 -m unittest discover -s tests -v |
| Real Android UI assertions | 14 passed. | artifacts/ui_test.0xpCz5/instrumentation.log |
| Process-restart restoration | Correct transaction restored with the same persisted receipt; capture passes record checking. | artifacts/evidence/20260907T102016Z_6c4dfecd/snapshot.json and verdict.json |
| UI image | Actual PNG visually inspected after the label/scroll patch; receipt and selected fields readable. | artifacts/evidence/20260907T101926Z_91f073da/screen.png; final provenance capture is in 20260907T102016Z_6c4dfecd. |
| Training/evaluation | No model calls, no Prime upload/publication. | Final inspection capture is explicitly ineligible for training. |
| Remaining integration | Full payment-specific 14-policy/70-verifier definitions, model action runner and Prime adapter are not implemented. | They must be implemented/tested separately before claiming benchmark readiness. |
| Known build warning | Java 8 language-target deprecation under Java 21 remains visible. | Complete JDK/jlink installation is required before retrying the Java-17 language target. |

These tests check different layers and overlap; 13 JVM tests, 15 Python tests and 14 UI assertions are not forty-two independent proofs or benchmark examples. The UI instrumentation uses direct widget calls and is not an accessibility-agent navigation test. Captures prove the recorded app state at inspection time, not broad financial correctness or performance on other tasks.

No banking backend, payment gateway, authentication keys, real transfers, Docker image or Prime environment was created. The Material UI and simulated transaction milestone is implemented. The next concrete step is to define and port the payment-specific policy/evidence contract before any model evaluation.

### Final cleanup

The temporary PaymentDemo_001 emulator was stopped, its private ADB server on port 5041 was stopped, and its disposable AVD directory /tmp/paymentdemo-ui.NQFAFn was deleted. These were generated test-device files, not app source or saved results; the device can be recreated from the installed SDK image. The first cleanup command inherited the host's Java 11 and was rejected by avdmanager. Repeating it with the documented JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 succeeded; no source patch or JDK replacement was needed. The final Python test rerun passed all 15 tests. APKs, screenshots, logs and JSON reports remain under this environment directory. No Docker resources were created during this implementation.

## Patch 009 — real model evaluation integration

The user authorized implementing the remaining runner, screenshots, full policy layer and Prime upload, then running one evaluation. The account was checked through Prime and is terrano09. The actor will run on this server's isolated KVM emulator; the environment and results will be stored on Prime. That is not Prime-hosted compute. A currently zero-priced OpenRouter vision model is required; the runner refuses paid or text-only models and reads credentials only from the environment.

actions.py defines exact supported JSON objects and safe text/target allowlists. device.py translates only those actions to explicit-device ADB commands, preserving command receipts. It captures live state before/after a unique UI dump, the original screenshot, private persisted state and the ordered event journal. It checks that these refer to the same stable episode. An isolated Tesseract 5.3.4 binary and English data were extracted under .tools/ocr rather than changing system packages; OCR reads the PNG and never generates or edits it.

policies.py registers 70 named functions from 14 policies and five methods each. Each named function evaluates its whole policy claim. Outcome policies use persisted state, live state, journal replay, accessibility and OCR. Generic policies inspect model text, action records, dispatch receipts, ADB spans and app events with shared full-contract guards. These are correlated inspections, not seventy independent models or five independent proofs. In particular, the UI and screenshot often show the same underlying state. Missing evidence produces a reasoned INVALID vote, not a guessed PASS.

scoring.py preserves PASS=1, INVALID=0, FAIL=-1 and support=0.5+0.1*passing_verifiers. Two passing votes meet the inclusive 0.7 threshold even if three disagree. All five invalid gives policy reward zero. Any failed policy gives episode -1; otherwise any invalid policy gives zero; otherwise all fourteen pass gives 1. Six task-stage statuses are separate progress diagnostics and do not add points to the final reward.

runner.py starts a new explicit episode, receives only model-generated actions, saves the unmodified response before execution, and records a screenshot/checkpoint after each response including rejected actions. It does not repair the action or fall back to scripted answers. Only the task goal, current visible UI, screenshot and execution error reach the actor; private state and verifier answers stay in the evidence folder. An early finish is rejected and consumes a step. Completion, 16 actions or a pipeline error stops the actor. The final checkpoint is updated with the signed terminal reward; earlier checkpoints remain provisional.

prime_env.py exposes the same Episode implementation through verifiers.MultiTurnEnv. Its one-function Rubric forwards the signed verdict and makes missing/inconsistent results explicitly INVALID. Construction/import does not launch Android. pyproject.toml adds package metadata, pinned dependencies and a source-only build allowlist; scripts/run_eval.sh and scripts/start_emulator.sh provide explicit launch controls. This turn adds no real payment backend and does not modify Java app behavior.

## Patch 010 — trace-binding regression before evaluation

The first expanded test run had 30 passing tests and one failure: test_model_action_mismatch_invalid. When stored model text differed from the dispatched action, the raw-text method could still pass while the other four became INVALID, yielding a policy FAIL under the approved threshold. generic_check now checks model text, action record and requested-action receipt equality before any strategy can vote. This classifies a harness/logging mismatch as INVALID for every method. This is a pipeline-integrity repair, not an actor correction or scoring-threshold change. The test rerun is required before launch.

Validation after Patch 010: all 31 tests pass. This includes an exhaustive test of all 243 five-vote combinations; that is one parameterized test, not 243 model episodes. An isolated .venv-eval was installed with verifiers 0.3.1 and datasets 5.0.1. The pre-existing Prime CLI uses verifiers 0.3.0 and was not modified. Package import/dataset construction under pinned 0.3.1 yielded exactly one row.

## Patch 011 — bounded upload and optional OCR failure handling

upload.py verifies all frozen artifact hashes before any remote write, requires a genuine model call, and checks that the active personal account is terrano09. It uploads one evaluation with every original per-step PNG and allowlisted JSON/XML/command logs, rejects credential-like text or payloads above 25 MiB, records a resumable upload receipt, and compares the returned screenshot hashes/log contents/reward. Browser rendering is not claimed from stored hashes.

An OCR process failure now marks only the screenshot-OCR channel unavailable; intact UI/state evidence remains usable. Original PNG collection is still required for this screenshot-inclusive run. The new disposable emulator is PaymentEval_001 under /tmp/payment-eval.VuEoHc with private ADB port 5041 and JWT-protected loopback gRPC. No Docker image/container is needed for this native run. The unchanged APK was rebuilt and installed; local and installed SHA256 both equal 6db0d97f03e6ef35c4e1443eabbaa68d17d54f9439ea58fc695c7d0d6eac8eb8.

The sandbox's file-update helper intermittently failed before applying patches. Full-file apply_patch additions were used with the current content preserved. This changes the editing mechanism only, not task/runtime behavior.

## Patch 012 — valid input focus was misclassified (runtime 0.2.1)

The first genuine model attempt, artifacts/model/20260907T115147Z_4983ee9a, made nine OpenRouter calls and completed all six task stages in 124.6 seconds. It saved ten original screenshots. Its original scorer reported FAIL=-1 because steps 2 and 5 tapped amount_input and note_input to focus them, and the harness incorrectly demanded enter_amount/enter_note mutation events for those focus-only taps. The saved post-action UI nodes prove focused=true in both cases. There was no app rejection and no invalid payment selection.

The original run and its hashes are unchanged. A separate audit_disposition.json marks it INVALID for benchmark/training use, with training_eligible=false, while preserving the original erroneous FAIL result. It must not be used as an agent failure or counted as the valid scored attempt.

New acceptance.py separates three claims: a focus tap is confirmed by the post-action focused UI node; text replacement is confirmed by the actual current input value, including a valid no-op replacement; business buttons require the matching app event. Explicit app rejection remains an agent failure. Missing focus/effect evidence is a pipeline issue, not an invented agent error. runner.py uses that helper. No task values, model output, threshold, reward formula or Java app logic changed. The package/runtime version is 0.2.1.

Seven new acceptance tests cover amount/note focus without mutation, unproven focus, no-op text replacement, wrong text effect, explicit app rejection and missing commit receipt. All 38 Python tests pass before the fresh rerun.

## Prime publication boundary

The safety review blocked source-package publication because exporting app source requires separate explicit approval. No source archive or APK was sent to Prime. The user was asked for that approval while the authorized local evaluation continued.

A safer results-only registration succeeded using Prime's metadata resolver, creating environment ID wvcycgdmw5xt6189qp2oilf4 owned by terrano09. It contains no published source version; querying its latest package tag correctly returns 404. This metadata record can associate uploaded evaluation results with the payment task. It is not a claim that the executable source package has been published or that Prime hosted the emulator. The locally built wheel/source archive and adapter remain available for publication after approval.

## Final evaluation and upload — runtime 0.2.1

The fresh run artifacts/model/20260907T115738Z_5f196c0e completed in 106.59 seconds using dots-studio/dots-3-note-preview:free. It made seven real model calls, executed seven unmodified model actions, and captured eight original PNGs. All six stages and all fourteen policies passed; episode reward is 1. This is one valid scored example, not a benchmark-wide success rate. The earlier nine-action attempt remains a separate harness-invalid audit record.

| Verified item | Exact result | Evidence |
|---|---|---|
| Python validation | 38 tests pass, including 243 vote combinations inside one test. | tests/; final unittest rerun |
| Installed APK | Build and installed SHA256 agree; Java UI/business logic was not changed in this evaluation patch. | installed_apk.json |
| Actor | dots-studio/dots-3-note-preview:free; 7 model calls and 7 actions. | model_calls.json; trajectory.jsonl |
| Task progress | Recipient 1/6, amount 2/6, account 3/6, note 4/6, keyboard dismissal remains 4/6, review 5/6, confirmation 6/6. | progress_history.json; checkpoints/ |
| Final policies | 14 PASS; final support is 0.8 for T5 and 0.9 for T6, 1.0 for the other twelve. | verdict.json |
| Individual evidence votes | 67 PASS, 3 INVALID, 0 FAIL; no conflicting PASS/FAIL votes. | verifier_results.json |
| Remaining visual uncertainty | T5.V4/T5.V5 cannot establish reviewed revision from the terminal UI/pixels. T6.V5 OCR did not reliably read the receipt. These votes remain INVALID. | Corresponding reason_code values in verdict.json |
| Screenshots | 8/8 original files, visually inspected step by step. | frames/000 through frames/007; SCREENSHOTS.md |
| Prime results | COMPLETED; total_samples=1; avg_score=1.0; is_hosted=false; terrano09 personal account. | prime_upload.json; prime_samples.json |
| Upload verification | All 8 screenshot hashes, all 78 exported text logs and the reward round-trip correctly. | prime_upload.json#/verification |
| Inference charges | Each of the seven model usage receipts reports cost=0. | model_calls.json; this does not price the already-owned server |
| Source publication | Blocked by safety review pending explicit code-export approval. Results-only environment has no published version/tag. | Environment ID wvcycgdmw5xt6189qp2oilf4; version_id=null |
| Cleanup | Emulator stopped, private ADB stopped, /tmp/payment-eval.VuEoHc deleted and dedicated ports released. No Docker resources created. | Final process/port/path checks |

Prime evaluation: https://app.primeintellect.ai/dashboard/evaluations/z5vigpg7179mu02c993tmfk9

The reviewed screenshots show the UI evolving from an empty form to a receipt for Alex, INR 500.00, account 1234 and Lunch. Receipt ID is 5a988be7-51fc-4d34-857e-a47dbe8260fd. The screenshot-OCR receipt verifier did not guess that identifier when its extracted text was insufficient; persisted state, live state, journal replay and accessibility confirmed completion instead. Two agreeing verifiers would suffice under the user-approved threshold, but this run's weakest policy has three passing verifiers.

The app-state, UI and screenshot channels are correlated. These counts are not seventy independent proofs, nor do they establish security of real payment processing. Prime's stored artifact identities and text logs were checked through its API; its logged-in browser rendering was not independently tested. The skill's evidence-led format is used here to distinguish these verified facts from the remaining publication/rendering boundaries.

The source package is built locally at artifacts/package-build/payment_transfer_001-0.2.1-py3-none-any.whl and the corresponding .tar.gz. The Prime wrapper loads with pinned verifiers 0.3.1 and has exactly one dataset row. It requires a prepared emulator and an explicit allow_eval flag; importing or publishing a package does not itself provision Android compute.

### Evaluation file tree and exact responsibilities

~~~text
payment_transfer_001/
├── pyproject.toml
├── README.md
├── IMPLEMENTATION_LOG.md
├── app/dummy_android_app/           # Unchanged, hash-checked Material APK source
├── payment_transfer_001/specs/task.json   # Human-facing fixed task
├── payment_transfer_001/
│   ├── __init__.py                 # Lazy package entry point, version 0.2.1
│   ├── actions.py                  # Strict JSON/types, tool/target/text allowlists
│   ├── acceptance.py               # Focus versus replacement versus business event
│   ├── device.py                   # Explicit ADB calls and frozen evidence capture
│   ├── policies.py                 # 70 named policy/evidence-bound checks
│   ├── scoring.py                  # Exact >=0.7 policy and signed episode scoring
│   ├── runner.py                   # Model loop, budget, checkpoints, frozen export
│   ├── prime_env.py                # Same Episode through verifiers.MultiTurnEnv
│   ├── upload.py                   # terrano09-only result upload and round-trip checks
│   ├── verifier.py                 # Existing strict transaction record checker
│   └── specs/
│       ├── task.json               # Bundled copy of the same fixed task
│       └── policies.json           # 14 policy claims, 70 IDs and scoring contract
├── scripts/
│   ├── build_apk.sh
│   ├── install_apk.sh
│   ├── test_ui.sh
│   ├── capture_evidence.py         # Original inspection-only collector
│   ├── start_emulator.sh           # New isolated AVD; refuses conflicting ports
│   └── run_eval.sh                 # Explicit real OpenRouter actor launch
├── tests/
│   ├── test_verifier.py
│   ├── test_capture.py
│   ├── test_policies.py
│   └── test_acceptance.py
└── artifacts/
    ├── preflight/                  # No-model readiness and rejection checks
    ├── package-build/
    └── model/
        ├── 20260907T115147Z_4983ee9a/ # Original harness-invalid attempt + audit
        └── 20260907T115738Z_5f196c0e/ # Valid PASS evaluation + Prime receipt
~~~

The editable Python environment (.venv-eval, about 450 MiB) and isolated OCR runtime (.tools, about 16 MiB) are retained because they are working dependencies, not disposable emulator disks. They are ignored by Git and excluded from the built distribution. The source task and bundled specs/task.json currently match exactly; future task-value changes must update both before rebuilding. No raw API key is written into source, reports, screenshots or upload commands.

The uploader also refuses a run containing audit_disposition.json with audit_status=INVALID. This prevents accidentally exporting the original erroneous score as a valid benchmark. That guard is part of the frozen 0.2.1 runtime used for the successful rerun.

Only generated temporary emulator storage was deleted; the SDK image can recreate it. No source, APK, successful/failed run evidence or other user's device/container was deleted. Future functional patches must append their cause, affected code, before/after behavior and test/run evidence to this file in the same change.
