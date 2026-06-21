# Observation And Action Schema

Both the ADB backend and the AndroidWorld backend now emit the same observation envelope: `mobile_observation.v1`.

## Observation fields

- `schema_version`: `mobile_observation.v1`
- `backend`: `adb` or `android_world`
- `task`, `task_id`, `episode_id`
- `screen`, `step`, `steps`, `max_steps`
- `reward`, `final_reward`, `exact_success`
- `reward_components`
- `reset_metadata`
- `elements`: compact UI elements, each with:
  - `element_index`
  - `element_id`
  - `text`
  - `role`
  - `clickable`
  - `focused`
  - `bounds`
- `ui`: full normalized accessibility/UI element list when `full_ui_tree` mode is used
- `ui_tree_xml`: backend UI tree payload when available
- `last_action`, `last_error`

## Action schema

Policies emit structured mobile actions using these tool names:

- `click_resource`
- `input_resource`
- `tap_coordinates`
- `press_back`
- `press_home`
- `swipe`
- `wait`
- `finish`

Arguments:

- `target` for resource-based actions
- `text` for `input_resource`
- `x`, `y` for `tap_coordinates`
- `x1`, `y1`, `x2`, `y2`, `duration_ms` for `swipe`

## Notes

- Resource-based actions should prefer `element_index`/`element_id` style targeting over raw coordinates when possible.
- Screenshot paths remain optional; the standardized contract in this repo is accessibility-tree-first plus indexed UI elements.
