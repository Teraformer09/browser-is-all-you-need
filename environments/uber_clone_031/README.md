# Uber Clone 031

This standalone task controls an offline Android demo through ADB. The requested
outcome is a Premium ride from Airport Road to City Centre, using the Premium cab
and CARD payment. Nothing is ordered or charged. The model sees UI observations
and screenshots, not the app's hidden verifier state.

The app, harness and verifier source are included. Saved evaluation artifacts,
virtual environments, SDKs, signing keys and generated APKs are not source files
and are excluded from the package. Installing this environment does not start an
emulator, launch a paid evaluation, or publish anything to Prime.

## Source layout

```text
uber_clone_031/
├── pyproject.toml
├── README.md
├── IMPLEMENTATION_LOG.md
├── POLICY_RUBRICS.md
├── Dockerfile
├── app/dummy_android_app/          # Manifest, resources and Android Java source
├── scripts/
│   ├── build_apk.sh
│   ├── start_emulator.sh
│   ├── install_apk.sh
│   ├── run_eval.sh
│   ├── check_saved_evidence.py
│   └── test_app_contract.sh
├── uber_clone_031/
│   ├── __init__.py                # Lazy Prime load_environment entry point
│   ├── cli.py                    # Explicitly authorized episode orchestration
│   ├── specs/
│   │   ├── task.json             # Single source of task parameters and limits
│   │   ├── policies.json         # 14 policies × 5 registered verifier IDs
│   │   ├── scoring.json          # Exact signed voting contract
│   │   ├── schemas/
│   │   ├── apps/uber_clone/
│   │   ├── topics/ride_booking/
│   │   └── generic/
│   ├── harness/
│   │   ├── actions.py            # Model action schema
│   │   ├── device.py             # Traced ADB and fresh UI reads
│   │   ├── episode.py            # Stage acceptance and recovery
│   │   ├── evidence.py           # Screenshots, state and per-step reports
│   │   ├── prompts.py            # Public model instructions
│   │   ├── readiness.py
│   │   ├── ocr.py
│   │   └── backend/              # Private, task-bundled legacy Android bridge
│   ├── agents/openrouter.py      # Model request and bounded transport retries
│   ├── verification/
│   │   ├── registry.py           # Versioned configuration and binding validation
│   │   ├── contracts.py          # Evidence-backed result/registration decorator
│   │   ├── checks.py             # Imports every policy implementation
│   │   ├── evidence_readers.py   # Read-only frozen evidence readers
│   │   ├── helpers.py
│   │   ├── generic/validity.py   # V1–V2: readiness and evidence integrity
│   │   ├── generic/interaction.py # G1–G4: format, permission, target, execution
│   │   ├── semantic.py           # S1: meaning of selected controls
│   │   ├── task_checks.py        # T1–T7: requested ride and action history
│   │   ├── records.py            # Six diagnostic workflow-stage checks
│   │   ├── progress.py
│   │   ├── scoring.py
│   │   └── runner.py
│   └── integrations/
│       ├── prime_env.py          # verifiers.MultiTurnEnv and signed reward adapter
│       └── prime_upload.py       # Explicit result-only upload and hash validation
└── tests/                         # Offline regressions and opt-in Android tests
```

## Rewards and evidence

Each verifier returns PASS = 1, INVALID = 0, or FAIL = -1. For each policy, support
is `0.5 + 0.1 × passing_verifiers`. At least `0.7` passes; all five INVALID returns
0; otherwise it fails. Two PASS votes therefore outvote three FAIL votes. This is
the agreed support rule, not 70% agreement or a calibrated probability. Correlated
channels and conflicting verdicts are retained in the report.

Any failed policy makes the episode reward -1. Otherwise any invalid policy makes
it 0; all 14 passing gives 1. Invalid episodes must be excluded explicitly before
training normalization. Six workflow-stage progress indicators are diagnostics,
not additional reward points. A successful tap does not prove a successful booking.

## Local commands

Run from this task directory. Python 3.11+, Java, Android SDK and an explicitly
selected KVM-capable emulator are required for Android execution.

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -p 'test_*.py'
bash scripts/build_apk.sh
ADB_SERIAL=emulator-5556 bash scripts/install_apk.sh
```

Only after approving an evaluation, configure `OPENROUTER_API_KEY` outside the
repository and run with a currently available free model:

```bash
ADB_SERIAL=emulator-5556 python3 -m uber_clone_031.cli \
  --confirm-eval --policy openrouter --model '<model-id>:free' \
  --output-dir artifacts/model
```

The scripted policy is a separate smoke test, never an LLM result. The harness
saves reset plus every action screenshot, state/UI snapshots, ADB receipts,
policy votes, progress, and final JSON. Historical runs keep their original model,
verifier version and artifact hashes; this refactor does not rescore them.

For an existing genuine model run, inspect the upload CLI before enabling a write:

```bash
python3 -m uber_clone_031.integrations.prime_upload --help
```

Prime is an integration boundary: local emulator execution and uploaded results
do not imply hosted KVM execution or a verified live dashboard UI.
