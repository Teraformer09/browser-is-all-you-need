# Reward Semantics

Reward values are now explicit:

- `final_reward=1.0`: exact task success. All required durable state checks passed.
- `final_reward=0.0`: exact task success was not reached.
- `reward` in `(0.0, 1.0)`: partial progress from shaped, component-based scoring.

## Form task

`DummyApkFormSearchTask` uses component-weighted shaped reward from:

- episode match
- screen match
- query match
- name match
- email match
- submitted
- no forbidden action
- no invalid action
- finish after success

`final_reward` stays binary and is only `1.0` when the exact-success subset is fully satisfied.

## Ride task

`RideBookingTask` uses fractional shaped reward equal to:

`successful_components / total_components`

This means a run that fills pickup/drop and chooses the correct ride, but never confirms the ride, will emit a partial reward above `0.0` and below `1.0`.

## Artifact contract

- `reward_trace.jsonl.reward`: shaped reward used for learning signal
- `reward_trace.jsonl.exact_success`: exact pass/fail flag
- `reward_trace.jsonl.reward_components`: component breakdown for audit/debug
- rollout and benchmark summaries include reset timing metrics and standard reward aggregates
