# Codex Context: Prime Intellect Android ADK RL Environments

Last updated: 2026-06-03

## Purpose

This file is the working context for AI agents editing this documentation set. Update it whenever the analysis, assumptions, commands, source list, or recommendation changes.

Project folder:

```text
prime-intellect-android-adk-rl-environments/
```

Required files:

```text
README.md
pyproject.toml
android_adk_rl_env/
configs/
tests/
requiremnt.md
codex.md
solutation.md
```

The filenames intentionally preserve the spelling requested by the user.

## User Goal

Create documentation for "Prime Intellect Android ADK RL Environments" based on:

- the AndroidWorld GitHub project,
- the Prime AndroidWorld environment page,
- the user-provided AndroidWorld task runbook,
- a requested final write-up covering AndroidWorld and alternatives.

## Working Interpretation

In this document set, "Android ADK RL" means RL/evaluation environments where an agent can interact with Android applications or Android device UI through an emulator, ADB/UIAutomator-style controls, or equivalent tooling.

If future work uses "ADK" to mean a specific vendor SDK, update this interpretation and revise the solution accordingly.

## Current Recommendation

Use AndroidWorld as the primary Prime Intellect candidate because it explicitly supports Android emulator/app interaction. Use BrowserEnv only when the target workflow has a usable web interface. Use AndroidLab as an external reference benchmark. Build a custom ADB/Appium/Gym wrapper only when native commercial app fidelity is required.

For the runnable scaffold in this folder, use the dependency-free mock Android device first. It provides a working task loop immediately and keeps the Android boundary isolated in `MockAndroidDevice`, which can later be replaced by ADB, UIAutomator, Appium, or AndroidWorld.

## Source Notes

Relevant sources:

- AndroidWorld: https://github.com/google-research/android_world
- AndroidWorld tasks guide: https://github.com/google-research/android_world/blob/main/docs/tasks_guide.md
- Prime AndroidWorld page: https://app.primeintellect.ai/dashboard/environments/primeintellect/androidworld
- Prime evaluation docs: https://docs.primeintellect.ai/tutorials-environments/evaluating
- Prime environments docs: https://docs.primeintellect.ai/verifiers/environments
- Prime Verifiers repository: https://github.com/PrimeIntellect-ai/verifiers
- AndroidLab: https://github.com/THUDM/Android-Lab

Facts verified during creation:

- AndroidWorld describes itself as an environment for building and benchmarking autonomous computer-control agents on a live Android emulator.
- AndroidWorld advertises 116 hand-crafted tasks across 20 apps and durable reward signals.
- AndroidWorld installation requires Android emulator setup, a Pixel 6/API 33 style AVD, emulator launch with `-grpc 8554`, and Python 3.11+.
- Prime evaluation docs use `prime eval run <environment>` and support hosted runs with `--hosted`.
- Prime Verifiers docs describe environments as reusable units for evaluation and RL training, with datasets/tasksets, harnesses/tools, and reward/rubric logic.

## Edit Protocol

When changing this folder:

1. Update `requiremnt.md` if the scope, constraints, assumptions, or acceptance criteria change.
2. Update `codex.md` if the AI-agent context, source list, recommendation, or implementation state changes.
3. Update `solutation.md` if the user-facing recommendation, commands, architecture, or comparison changes.
4. Keep all three files aligned on terminology and facts.
5. Prefer explicit dates for time-sensitive statements.
6. Use source URLs directly in Markdown instead of opaque citation labels.

## Documentation Style

- Keep commands copy-pasteable.
- Prefer tables for environment comparison and checklist-style requirements.
- Label assumptions clearly.
- Do not imply that AndroidWorld includes commercial app workflows unless a task/APK has been added and validated.
- Call out setup cost and emulator/KVM constraints.
- For new AndroidWorld tasks, prefer durable validation through SQLite, files, settings, or explicit app state.

## Implementation State

Created on 2026-06-03:

- Added `requiremnt.md`.
- Added `codex.md`.
- Added `solutation.md`.
- Added `pyproject.toml`.
- Added `README.md`.
- Added `android_adk_rl_env/` Python package.
- Added one runnable task: `CreateNoteTask`.
- Added local CLI runner: `python3 -m android_adk_rl_env.runner --task create_note --policy scripted`.
- Added tests under `tests/`.

No Android SDK, emulator, APK, or Prime environment was installed. The current task uses a deterministic mock Android notes app so it can run in this workspace.

## Runnable Project Shape

Current files:

```text
android_adk_rl_env/
  actions.py
  env.py
  runner.py
  tasks/
    base.py
    create_note.py
configs/eval/smoke.toml
tests/test_create_note.py
```

Task contract:

```text
CreateNoteTask
  -> goal: create a specific note
  -> environment: MockAndroidDevice
  -> actions: open_app, tap, input_text, submit, navigate_back
  -> validator: device.has_note(title, body)
  -> reward: 1.0 on exact durable note match, otherwise 0.0
```

Run:

```bash
python3 -m android_adk_rl_env.runner --task create_note --policy scripted
```

Test:

```bash
python3 -m unittest discover -s tests
```

## Open Questions

- Does the Prime-hosted `primeintellect/androidworld` package currently expose environment-specific arguments beyond sample count and rollout count?
- Is the target "ADK" meant generically as Android device/app control, or a specific agent development kit/API?
- Are target commercial workflows required to run in native Android apps, or are web equivalents acceptable?
- Will custom APKs be evaluated locally only, or packaged into a Prime environment for hosted execution?


## APK-Backed Dummy App Status

Implemented on 2026-06-03:

- Added a minimal Java Android app at `dummy_android_app/` with package `com.primeintellect.dummyrl`.
- Added direct APK build/install scripts under `scripts/`.
- Added `AdbDevice`, an ADB/UIAutomator action layer that finds controls by resource ID, taps bounds, verifies focus, and types text.
- Added `DummyApkFormSearchTask`, which searches, fills name/email fields, submits the form, and validates durable SharedPreferences state.
- Added documentation at `docs/dummy_apk_rl_env.md`.

Verified on connected Android device `localhost:5555`:

```bash
./scripts/build_dummy_apk.sh
./scripts/install_dummy_apk.sh
python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --compact
```

Result: `success=true`, `reward=1.0`, status text `Submitted: Ada Lovelace <ada@example.com>`.
