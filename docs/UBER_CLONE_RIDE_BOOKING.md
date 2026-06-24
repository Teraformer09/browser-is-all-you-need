# Uber Clone Ride Booking

Last updated: 2026-06-23

## What This Is

The repo now includes a ride-booking mock app that presents an Uber-like booking flow inside the dummy APK package `com.primeintellect.dummyrl`.

The ride surface is designed for agent evaluation, not for production dispatch. It keeps the important booking ids stable so benchmark policies and scripted actions can drive the flow.

## User Flow

1. Open the app.
2. Select the ride type.
3. Enter a destination.
4. Select a cab type.
5. Select payment.
6. Confirm the ride.

The ride task state is stored in shared preferences and is used by the verifier and reward calculation.

## App Structure

- `dummy_android_app/src/com/primeintellect/dummyrl/MainActivity.java`
  - Builds the home form and the ride booking surface.
  - Exposes stable ids such as `pickup_input`, `drop_input`, `ride_type_ride`, `ride_option_mini`, `payment_upi`, and `confirm_ride_button`.
- `android_adk_rl_env/tasks/ride_booking.py`
  - Defines the ride task model and scripted execution.
  - Launches the app with `start_screen=ride`.
- `android_adk_rl_env/policies/openai_policy.py`
  - Produces structured actions for the ride flow when `OPENAI_API_KEY` is configured.
- `android_adk_rl_env/eval_runner.py`
  - Runs a task spec against ADB and computes success/reward.
- `tasks/uber_clone/*.yaml`
  - The 30-task benchmark suite for the ride booking flow.

## Benchmark Suite

The `tasks/uber_clone/` directory contains 30 YAML tasks:

- `uber_clone_001.yaml` through `uber_clone_030.yaml`

Each task varies at least one of:

- ride type
- destination
- cab type
- payment type

The reward check is registered as `ride_booking_exact`.

## Verified Behavior

Validated on 2026-06-23:

- `python3 -B -m android_adk_rl_env.cli eval --task tasks/uber_clone/uber_clone_001.yaml --policy scripted --backend adb`
- result: success
- exact success: `true`

Screenshot artifact:

- [ride_clone_screen.png](/tmp/ride_clone_screen_updated.png)

## How To Run

Build and install the APK:

```bash
bash scripts/build_dummy_apk.sh
ADB_SERIAL=127.0.0.1:15555 bash scripts/install_dummy_apk.sh
```

Run a scripted eval:

```bash
python3 -B -m android_adk_rl_env.cli eval   --task tasks/uber_clone/uber_clone_001.yaml   --policy scripted   --backend adb   --max-steps 12
```

Run the full 30-task benchmark with a model policy once `OPENAI_API_KEY` is set:

```bash
python3 -B -m android_adk_rl_env.cli benchmark   --tasks-dir tasks/uber_clone   --policy openai   --samples-per-task 10   --pass-k 2 3 5 10   --max-steps 12   --output artifacts/benchmarks/uber_clone_openai
```

## Current Limitation

`OPENAI_API_KEY` is not set in the current environment, so the OpenAI-backed benchmark has not been executed here.
