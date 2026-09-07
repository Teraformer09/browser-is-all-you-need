# DemoCart / Amazon Cart 001

Search separately for Nimbus Wireless Headphones, Trail Steel Water Bottle and Metro Laptop Backpack. Add one of each, no extras, and open the cart. The expected subtotal is INR 4,997. The app is a controlled offline Android demo, with Material Views components. Its Java app, Python action harness, evidence collection, policy verifiers and Prime adapter are packaged together.

Version 0.2.0 uses the common task layout below. The earlier ten-action, eleven-screenshot run was `scripted-ui-validation (no model)`. It remains a scripted run. This version adds a genuine OpenRouter runner, but no new model evaluation was launched during this cleanup. Generated files and historical evaluation artifacts are excluded from Git and distribution packages.

## File tree

```text
amazon_cart_001/
├── pyproject.toml
├── README.md
├── IMPLEMENTATION_LOG.md
├── app/shopping_android_app/
│   ├── AndroidManifest.xml
│   ├── build.gradle
│   ├── settings.gradle
│   ├── gradle.properties
│   ├── gradlew + gradle/wrapper/
│   ├── app/build.gradle
│   ├── app/src/test/java/.../AppStateTest.java
│   ├── res/
│   └── src/.../
│       ├── MainActivity.java
│       ├── AppState.java
│       ├── StateStore.java
│       └── VerifierStateProvider.java
├── amazon_cart_001/
│   ├── __init__.py
│   ├── cli.py
│   ├── specs/
│   │   ├── task.json
│   │   ├── app_contract.json
│   │   ├── policies.json
│   │   └── scoring.json
│   ├── harness/
│   │   ├── actions.py
│   │   ├── device.py
│   │   ├── acceptance.py
│   │   ├── episode.py
│   │   ├── evidence.py
│   │   └── prompts.py
│   ├── agents/
│   │   ├── scripted.py
│   │   └── openrouter.py
│   ├── verification/
│   │   ├── contracts.py
│   │   ├── registry.py
│   │   ├── evidence_readers.py
│   │   ├── generic/validity.py
│   │   ├── generic/interaction.py
│   │   ├── semantic.py
│   │   ├── task_checks.py
│   │   ├── records.py
│   │   ├── progress.py
│   │   └── scoring.py
│   └── integrations/
│       ├── prime_env.py
│       └── prime_upload.py
├── scripts/
│   ├── build_apk.sh
│   ├── start_emulator.sh
│   ├── install_apk.sh
│   └── run_eval.sh
└── tests/
    ├── test_layout_contract.py
    ├── test_task_checks.py
    └── test_policies.py
```

Task-specific extras are retained where real functionality exists: payment has Android instrumentation/capture tests; DemoCart has `Catalog.java`, vector product illustrations, its scripted demonstration CLI and `integrations/legacy_scripted.py` for the immutable historical scripted export. No empty matching files are manufactured.

## What the files do

| Files | Code responsibility | Validation or boundary |
|---|---|---|
| `specs/task.json` | The only task definition; its values and step budget drive the actor instruction and expected outcome. | The duplicate root task file is removed. Registry checks reject missing or incompatible configuration. |
| `MainActivity.java`, `AppState.java`, `StateStore.java` | Render controls, validate business actions, persist state and record action acceptance. | `AppState.java` (formerly `ShoppingState.java`) handles searches, cart quantities and operation history. `Catalog.java` defines six fictional offline products. The read-only journal verifier independently replays accepted operations and compares reconstructed business state. There is no Amazon login, live listing, order, checkout or purchase. |
| `harness/actions.py`, `acceptance.py`, `episode.py` | Validate JSON and permitted targets, execute fresh UI actions, separate tool execution from app acceptance, reject an early finish. | Malformed actions are controlled errors; the actor is not repaired or silently replaced by a script. |
| `device.py`, `evidence.py` | Capture reset plus each action screenshot, UI tree, persisted state, read-only runtime snapshot, journal and ADB receipts. | Hashes and episode identities bind evidence; OCR is optional and cannot fabricate a missing vote. |
| `verification/` | Evaluate 14 policies using five registered strategies each; expose reasons, evidence references and conflicting votes. | Read-only inspection; no verifier completes the task for the actor. |
| `integrations/prime_env.py`, `prime_upload.py` | Expose the same episode through `verifiers.MultiTurnEnv`; upload an explicitly selected genuine model result with original logs/screenshots. | Loading alone starts nothing. Local KVM execution and uploaded results are not Prime-hosted compute. |
| `pyproject.toml`, build scripts | Package the Python implementation and Android source; build the APK using pinned Gradle/Android dependencies. | SDK/JDK paths select installed tools. Cache/temp outputs default to task-local artifacts. No generated APKs, signing keys, caches or saved runs are committed. |

## Exact policy and reward contract

V1–V2 check specification/capability readiness and evidence integrity. G1–G4 check action format, permission, target availability and execution. S1 checks task-bound semantic selections. T1 exact three product identities; T2 quantity one each; T3 unit prices/currency; T4 three distinct search-to-add links; T5 subtotal/counter arithmetic; T6 cart review screen; T7 accepted action history.

Every verifier returns PASS = 1, INVALID = 0, FAIL = -1. A policy's support is `0.5 + 0.1 * passed_verifiers`; `>= 0.7` passes. All five INVALID returns 0; otherwise insufficient support returns -1. Two PASS votes therefore outweigh three FAIL votes. This is not 70% agreement, not a probability and not a weighted sum of stages.

Any failed policy makes the episode -1; otherwise any invalid policy makes it 0; otherwise all fourteen passing gives 1. Pipeline-invalid episodes must be excluded explicitly before training normalization. Six workflow-stage indicators show progress separately from terminal reward. Evidence channels are correlated; five registrations do not imply five independent proofs. If a channel cannot establish a policy's full claim, it returns INVALID, not a guessed PASS.

## Commands

Run from this task directory. Keep credentials outside source files. Installing and offline tests do not start an evaluation:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -p 'test_*.py'
```

For an app build, point `ANDROID_SDK_ROOT` and `JAVA_HOME` at installed tools; `GRADLE_BIN` may point at an existing Gradle 8.9 executable. Build outputs stay in this task. Set `GRADLE_USER_HOME` and `TMPDIR` under `/data/Tirtha` when using the restricted server workspace.

```bash
bash scripts/build_apk.sh
```

After explicitly preparing/installing on a chosen emulator, a separately approved model evaluation can be launched with:

```bash
python3 -m amazon_cart_001.cli \
  --confirm-eval --serial emulator-5556 \
  --apk app/shopping_android_app/app/build/outputs/apk/debug/app-debug.apk \
  --output-dir artifacts/model --model '<approved-model-id>:free'
```

The runner requires `OPENROUTER_API_KEY` and checks current zero-price/image-input model capability at run time. It does not authorize paid-model fallback.

Saved runs contain per-action frames, trajectory and ADB logs, model request receipts, policy results, progress history, final verdict, metadata and a hash manifest. Prime uploading is a separate explicit action:

```bash
python3 -m amazon_cart_001.integrations.prime_upload --help
```

Offline test fixtures are not model evaluations. Previous live UI validation does not prove the renamed/model-enabled package has completed a new live rollout. No such rollout or new Prime upload was performed as part of this cleanup.
