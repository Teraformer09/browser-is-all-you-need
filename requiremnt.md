# Requirements: Prime Intellect Android ADK RL Environments

Last updated: 2026-06-03

## Objective

Produce a concise technical assessment of Prime Intellect environments that can support Android app/device interaction for reinforcement learning and evaluation workflows.

The primary question is:

> Which Prime Intellect environment should be used for Android ADK-style RL tasks, and what are the viable alternatives when the target workflows require commercial Android apps such as Amazon, DoorDash, or Uber?

## Source Inputs

Use these references as source material:

- Google Research AndroidWorld repository: https://github.com/google-research/android_world
- AndroidWorld task guide: https://github.com/google-research/android_world/blob/main/docs/tasks_guide.md
- Prime AndroidWorld environment page: https://app.primeintellect.ai/dashboard/environments/primeintellect/androidworld
- Prime environment evaluation docs: https://docs.primeintellect.ai/tutorials-environments/evaluating
- Prime Verifiers environment docs: https://docs.primeintellect.ai/verifiers/environments
- User-provided AndroidWorld runbook included in the request

## Scope

The deliverable must cover:

- AndroidWorld as the main Prime Intellect candidate.
- Whether AndroidWorld supports native Android app interaction.
- Whether AndroidWorld includes commercial apps such as Amazon, DoorDash, or Uber.
- Prime CLI evaluation flow for `primeintellect/androidworld`.
- Local AndroidWorld development flow for upstream task creation.
- How to add an APK-backed task to AndroidWorld.
- Browser-based alternatives for web versions of target services.
- External Android benchmark alternatives such as AndroidLab.
- Custom Android control wrappers using ADB, UIAutomator, Appium, or Gym-style interfaces.

## Functional Requirements

1. Identify the best-fit Prime Intellect environment for Android ADK RL work.
2. Explain AndroidWorld's task model:
   - task class generates a goal,
   - setup initializes app/device state,
   - agent interacts with the emulator,
   - validator checks app/device state,
   - reward is returned as success or failure.
3. Document at least three run modes:
   - upstream local emulator,
   - Dockerized Android runtime,
   - Prime Intellect environment evaluation.
4. Include command examples for:
   - installing/running AndroidWorld locally,
   - running a single task,
   - running a task subset,
   - running Prime evaluation,
   - checking Prime CLI help/environment metadata.
5. Document task extension steps:
   - inspect Android package/storage,
   - create a `TaskEval` subclass,
   - register the task,
   - test with `minimal_task_runner.py`,
   - run through `run.py`.
6. Document APK extension steps:
   - add APK to install path,
   - rebuild runtime/image,
   - verify package install,
   - add launch mapping,
   - add optional setup class.
7. Provide an environment comparison table with AndroidWorld, BrowserEnv, AndroidLab, and custom ADB/Appium wrapper.
8. Provide a recommendation and next steps.

## Non-Functional Requirements

- Be explicit about limitations and assumptions.
- Prefer durable validators such as SQLite, files, or device state over screenshot-only checks.
- Keep setup instructions practical and reproducible.
- Mark Prime CLI commands that may vary by published environment version.
- Avoid claiming support for commercial Android apps unless verified by the environment/task set.
- Keep the documents suitable as AI-agent context for future implementation work.

## Key Facts To Preserve

- AndroidWorld is an Android emulator benchmark for autonomous agents.
- AndroidWorld currently advertises 116 hand-crafted tasks across 20 apps with randomized parameters.
- AndroidWorld requires Android SDK/AVD setup for direct local use.
- Upstream local flow expects Python 3.11 or newer.
- Prime evaluation flow should be checked with:

```bash
prime env info primeintellect/androidworld
prime eval run primeintellect/androidworld --help
```

- AndroidWorld is the only Prime Intellect candidate identified here with explicit native Android emulator/app interaction.
- AndroidWorld does not provide built-in tasks for Amazon, DoorDash, or Uber in the provided source material.
- BrowserEnv can be used only for web UIs, not native Android app screens.
- AndroidLab is a relevant external benchmark, not a Prime Intellect environment.
- Custom Android wrappers are possible but high effort and require bespoke reward/state extraction.

## Acceptance Criteria

The documentation work is complete when this folder contains:

- `requiremnt.md`: requirements and acceptance criteria.
- `codex.md`: AI-agent context and change protocol.
- `solutation.md`: the final solution document for Prime Intellect Android ADK RL Environments.

Each file should be readable independently, while sharing the same facts and terminology.

The runnable project work is complete when this folder also contains:

- A Python package that can run without Android SDK or network access.
- One AndroidWorld-inspired task with a goal, initialization, Android-style actions, durable validation, and reward.
- A CLI command that completes the task with a scripted policy.
- A test suite proving the task succeeds and rejects incorrect app state.

Minimum runnable command:

```bash
python3 -m android_adk_rl_env.runner --task create_note --policy scripted
```

Minimum verification command:

```bash
python3 -m unittest discover -s tests
```


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
