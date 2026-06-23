# Next Handoff Priority Scope

Last updated: 2026-06-22

This document intentionally narrows the next round of work to the highest-value unresolved items.

The goal is to prevent the next pass from spending time on more A/C/F polish while Pillars B and D remain at zero.

## Scope For The Next Round

Only three areas should be treated as priority work:

1. Resolve the `127.0.0.1:15555` snapshot question one way or the other
2. Sanity-check and harden the Prime live-eval interpretation
3. Start Pillar B or Pillar D with real implementation work

## 1. Snapshot Question On `127.0.0.1:15555`

Current known facts:

- `127.0.0.1:15555` is the current primary live serial
- it is an ADB-over-TCP serial, not a console-mapped `emulator-####` serial
- raw snapshot commands on that serial fail with shell exit code `1`
- raw snapshot commands on `emulator-5556` succeed
- the repo now correctly degrades the TCP-attached path to `full` reset

What is still unresolved:

- whether `127.0.0.1:15555` is only a local AVD attached in an avoidable topology
- or whether it is a path that will structurally never support console snapshot commands

Required next action:

### Option A: Attempt relaunch as a console-mapped emulator

If the current `127.0.0.1:15555` device is a local emulator that can be relaunched:

- relaunch it in the standard console-mapped form
- verify whether it appears as `emulator-####`
- retry:
  - `adb -s <console-serial> emu avd snapshot list`
  - `adb -s <console-serial> emu avd snapshot save <name>`
  - `adb -s <console-serial> emu avd snapshot load <name>`
- then run one repo-level `RESET_MODE=snapshot` eval through the standard CLI

Definition of done:

- either snapshot works on the primary path after relaunch
- or there is a clear record that this path cannot be made console-mapped in the current setup

### Option B: Declare the topology unsupported for snapshot speed

If the path is genuinely remote or must remain TCP-attached:

- document explicitly that snapshot acceleration is unavailable on this topology by design
- state that speed work on this path depends on:
  - more console-capable pooled emulators
  - or the Pillar A2 hybrid fast-path backend

Definition of done:

- the docs stop implying snapshot is "basically handled"
- the speed strategy is stated honestly for the actual deployed topology

## 2. Prime Live-Eval Sanity Check

Current known facts from `artifacts/prime_eval_android_adk/live_20260622/prime_eval.log`:

- live Prime eval completed
- environment section is present
- model section is present
- step trace is present
- reward summary is present
- `has_final_env_response` is present
- no `Traceback` block was observed
- no top-level `Exception` block was observed
- final reward was `0.0`
- average turns were `6.0`

Interpretation:

- this looks like a genuine model attempt that failed the task
- it does not look like an early harness crash being silently scored as zero

What the next round should do:

- record the exact model / provider / environment tuple prominently in the docs
- inspect the rollout trace for the highest-leverage failure mode
- make one targeted improvement only
  - prompt hardening
  - action normalization
  - field-overtyping prevention
  - element-lookup recovery
- rerun one live Prime eval after that specific change

Definition of done:

- either reward improves measurably
- or the repo has a precise written diagnosis of the dominant model-failure mode

## 3. Start Pillar B Or Pillar D

This is the most important strategic constraint.

The next round should not primarily deepen Pillars A, C, or F again unless it directly supports one of the two items below.

### Preferred path: Pillar B

Implement the first cross-app benchmark family.

Recommended minimum slice:

- one cross-app task family
- at least two apps involved
- seeded initial state
- durable verifier
- one runnable task template
- one held-out parameter variant

Definition of done:

- the repo contains a real cross-app benchmark path, not just a design note

### Alternative path: Pillar D

Run the first real training loop.

Recommended minimum slice:

- choose one current task family
- train with the existing Prime / RL integration
- save one learning-curve artifact
- compare before vs. after on held-out instances

Definition of done:

- the repo contains one real trainability result, not just trainer compatibility

## What Should Not Be The Main Focus Next Round

- more general documentation polish
- more packaging detail
- more throughput prose without new measured pool sizes
- more status reshuffling across existing markdown
- more benchmark polish that does not touch B or D

## Suggested Execution Order

1. Resolve the snapshot topology question on `127.0.0.1:15555`
2. Do the Prime sanity-improvement loop once
3. Start Pillar B or D immediately after that

## Success Condition For The Next Round

The next round should produce at least one of these:

- snapshot support restored on the main live path
- a definitive unsupported-topology statement with a concrete alternative speed strategy
- a better Prime live-eval result or a precise model-failure diagnosis
- the first implemented cross-app benchmark family
- the first real training artifact
