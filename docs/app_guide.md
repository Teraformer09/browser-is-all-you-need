# App Guide: Writing RL-Friendly Dummy APKs

Last updated: 2026-06-03

This guide explains how to design dummy Android apps, such as Uber-like, DoorDash-like, shopping, banking, or booking apps, so they work well for RL training and benchmarking.

The core rule is simple:

```text
The app must expose stable UI targets, deterministic reset behavior, and durable machine-readable reward state.
```

A pretty UI is not enough. An RL app must be easy for an agent to observe, act on, reset, and grade.

## 1. What An RL Dummy App Needs

Every RL-ready dummy APK should provide these pieces:

| Requirement | Why it matters |
|---|---|
| Stable package name | ADB needs a fixed app identifier. |
| Stable resource IDs | The policy/environment needs reliable click/input targets. |
| Deterministic task state | Episodes must be repeatable. |
| Reset support | Every episode must start clean. |
| Durable state | Reward must be read from storage, not guessed from screenshots. |
| Explicit completion state | The env must know when the task is done. |
| Valid/invalid user paths | RL needs failure cases and partial progress. |
| Task variants | Benchmarking needs more than one fixed example. |

## 2. Recommended Project Shape

For each dummy app, keep this structure:

```text
dummy_android_app/
  AndroidManifest.xml
  res/values/ids.xml
  res/values/styles.xml
  src/com/example/dummyapp/MainActivity.java
```

For multiple apps, use separate folders:

```text
dummy_apps/
  ride_app/
  food_delivery_app/
  shopping_app/
```

Each app should have its own package:

```text
com.primeintellect.dummyride
com.primeintellect.dummyfood
com.primeintellect.dummyshop
```

Do not reuse the same package name for different apps unless you intentionally want one app to replace another during install.

## 3. Stable Resource IDs

Every field, button, important label, list item, and final status view needs a stable ID.

Example `ids.xml` for an Uber-like ride app:

```xml
<resources>
    <item name="pickup_input" type="id" />
    <item name="destination_input" type="id" />
    <item name="ride_type_spinner" type="id" />
    <item name="search_rides_button" type="id" />
    <item name="ride_option_standard" type="id" />
    <item name="ride_option_premium" type="id" />
    <item name="confirm_ride_button" type="id" />
    <item name="status_text" type="id" />
</resources>
```

Example `ids.xml` for a DoorDash-like food app:

```xml
<resources>
    <item name="restaurant_search_input" type="id" />
    <item name="restaurant_search_button" type="id" />
    <item name="restaurant_result_card" type="id" />
    <item name="menu_item_burger" type="id" />
    <item name="menu_item_fries" type="id" />
    <item name="add_to_cart_button" type="id" />
    <item name="cart_button" type="id" />
    <item name="checkout_button" type="id" />
    <item name="status_text" type="id" />
</resources>
```

Avoid IDs like:

```text
button1
textView7
temp_id
```

Use semantic IDs:

```text
confirm_ride_button
checkout_button
payment_method_card
```

## 4. Durable Reward State

The reward should come from durable app state. In a simple dummy app, use `SharedPreferences`.

Example ride app final state:

```xml
<map>
    <string name="pickup">Home</string>
    <string name="destination">Airport</string>
    <string name="ride_type">Standard</string>
    <boolean name="searched" value="true" />
    <boolean name="confirmed" value="true" />
</map>
```

Example food app final state:

```xml
<map>
    <string name="restaurant">Prime Burger</string>
    <string name="selected_item">Burger</string>
    <boolean name="added_to_cart" value="true" />
    <boolean name="checked_out" value="true" />
</map>
```

The environment can read this with:

```bash
adb shell run-as <package> cat shared_prefs/<state_file>.xml
```

Reward should not depend only on:

```text
screen text
screenshot matching
button color
visual position
```

Those are useful observations, but weak reward signals.

## 5. App State Design

Use explicit keys for every task requirement.

Bad:

```text
status = done
```

Good:

```text
pickup = Home
destination = Airport
ride_type = Standard
searched = true
confirmed = true
```

This lets reward be precise and shaped:

```text
+0.20 pickup correct
+0.20 destination correct
+0.20 ride type correct
+0.20 searched true
+0.20 confirmed true
```

## 6. Reset Behavior

Every episode must start clean.

The environment usually resets with:

```bash
adb shell pm clear <package>
adb shell am start -W -S -n <package>/.MainActivity
```

Therefore the app must tolerate fresh startup with no saved state.

On first launch:

```text
all text fields empty
all booleans false
status = waiting
cart/order/ride empty
```

Do not preload hidden success state.

## 7. Screen Flow Design

Start with one-screen apps, then add multi-screen flows.

Good first task:

```text
input pickup
input destination
choose ride type
confirm ride
```

Harder later task:

```text
search pickup
select autocomplete result
search destination
select route
choose ride type
confirm ride
rate driver
```

For RL training, difficulty should increase gradually.

Recommended levels:

| Level | App behavior |
|---|---|
| 1 | Single screen, fixed fields, one submit button. |
| 2 | Two screens, simple navigation. |
| 3 | Search results or menu list. |
| 4 | Cart/order state with multiple items. |
| 5 | Distractor buttons and invalid choices. |
| 6 | Dynamic task variants. |

## 8. Task Variants

Do not train only on one hardcoded task forever.

Instead define variants:

Ride app examples:

```json
{"pickup": "Home", "destination": "Airport", "ride_type": "Standard"}
{"pickup": "Office", "destination": "Gym", "ride_type": "Premium"}
{"pickup": "Hotel", "destination": "Museum", "ride_type": "XL"}
```

Food app examples:

```json
{"restaurant": "Prime Burger", "item": "Burger", "quantity": 1}
{"restaurant": "Sushi Lab", "item": "Salmon Roll", "quantity": 2}
{"restaurant": "Taco House", "item": "Veg Taco", "quantity": 3}
```

A benchmark should evaluate held-out variants that were not used during training.

## 9. Reward Function Pattern

A task class should expose:

```python
def expected_state(self) -> dict[str, str]:
    return {
        "pickup": self.pickup,
        "destination": self.destination,
        "ride_type": self.ride_type,
        "confirmed": "true",
    }
```

Then implement:

```python
def reward_components_from_prefs(self, prefs_xml: str) -> dict[str, bool]:
    state = self.state_from_prefs(prefs_xml)
    expected = self.expected_state()
    return {key: state.get(key) == value for key, value in expected.items()}


def shaped_reward_from_prefs(self, prefs_xml: str) -> float:
    components = self.reward_components_from_prefs(prefs_xml)
    return sum(components.values()) / len(components) if components else 0.0


def reward_from_prefs(self, prefs_xml: str) -> float:
    components = self.reward_components_from_prefs(prefs_xml)
    return 1.0 if components and all(components.values()) else 0.0
```

Use both:

```text
shaped_reward -> helps RL learn
final_reward  -> measures real task success
```

## 10. UI Observation Quality

The agent should be able to observe useful UI state through UIAutomator XML.

Make sure important widgets expose:

```text
resource-id
text
content-desc when useful
focused state
clickable state
```

For image buttons or icons, set content descriptions:

```java
cartButton.setContentDescription("Cart");
checkoutButton.setContentDescription("Checkout");
```

Avoid controls that are invisible to UIAutomator unless you also expose state elsewhere.

## 11. Avoid Fragile Coordinate-Only Apps

ADB can tap coordinates, but RL should prefer resource IDs.

Bad:

```text
Tap x=341 y=829
```

Good:

```json
{"action": "click_resource", "target": "confirm_ride_button"}
```

Coordinate-only tasks break when:

```text
screen size changes
font scale changes
keyboard appears
layout shifts
```

## 12. Handling Text Input

Text inputs should be single-line when possible:

```java
pickupInput.setSingleLine(true);
destinationInput.setSingleLine(true);
```

After typing into the last field, the environment may call:

```bash
adb shell input keyevent KEYCODE_BACK
```

This hides the keyboard before tapping buttons.

Make sure submit buttons are still reachable after the keyboard closes.

## 13. App Validation Rules

The app should reject incomplete submissions.

Example:

```java
if (pickup.length() == 0 || destination.length() == 0) {
  statusText.setText("Status: missing fields");
  saveState(false);
  return;
}
```

Do not silently accept empty or wrong state.

This creates meaningful negative feedback for RL.

## 14. Example: Uber-Like Dummy App

Goal:

```text
Book a Standard ride from Home to Airport.
```

UI:

| ID | Type | Purpose |
|---|---|---|
| `pickup_input` | EditText | Pickup field. |
| `destination_input` | EditText | Destination field. |
| `ride_type_standard` | Button | Select Standard ride. |
| `ride_type_premium` | Button | Distractor ride type. |
| `confirm_ride_button` | Button | Confirm booking. |
| `status_text` | TextView | Final status. |

State:

```text
pickup
destination
ride_type
confirmed
```

Reward:

```text
+0.25 pickup correct
+0.25 destination correct
+0.25 ride_type correct
+0.25 confirmed true
```

Final success:

```text
pickup == Home
AND destination == Airport
AND ride_type == Standard
AND confirmed == true
```

## 15. Example: DoorDash-Like Dummy App

Goal:

```text
Order one Burger from Prime Burger and checkout.
```

UI:

| ID | Type | Purpose |
|---|---|---|
| `restaurant_search_input` | EditText | Restaurant search. |
| `restaurant_search_button` | Button | Search. |
| `restaurant_result_prime_burger` | Button | Select restaurant. |
| `menu_item_burger` | Button | Select burger. |
| `menu_item_salad` | Button | Distractor item. |
| `add_to_cart_button` | Button | Add item. |
| `checkout_button` | Button | Checkout. |
| `status_text` | TextView | Final status. |

State:

```text
restaurant
selected_item
added_to_cart
checked_out
```

Reward:

```text
+0.25 restaurant correct
+0.25 selected_item correct
+0.25 added_to_cart true
+0.25 checked_out true
```

Final success:

```text
restaurant == Prime Burger
AND selected_item == Burger
AND added_to_cart == true
AND checked_out == true
```

## 16. Benchmark Design

Each app should support benchmark configs like:

```json
{
  "task": "ride_booking",
  "episodes": 20,
  "variants": [
    {"pickup": "Home", "destination": "Airport", "ride_type": "Standard"},
    {"pickup": "Office", "destination": "Gym", "ride_type": "Premium"}
  ]
}
```

Metrics:

```text
success_rate
average_final_reward
average_shaped_reward
average_steps
invalid_action_rate
resource_not_found_rate
adb_error_rate
time_per_episode
```

Do not report only one success/failure number. Save full trajectories for debugging.

## 17. Recommended App Difficulty Progression

Start simple:

```text
single screen
few fields
no scrolling
clear submit button
```

Then add complexity:

```text
scrolling
multi-screen navigation
lists
distractors
quantity controls
modal dialogs
held-out variants
```

Avoid starting with a complex Uber clone. Build a small deterministic ride app first, then grow it.

## 18. Common Mistakes

| Mistake | Problem |
|---|---|
| No resource IDs | Agent cannot reliably act. |
| Reward from screenshot only | Fragile and hard to debug. |
| No reset path | Episodes contaminate each other. |
| One fixed task forever | Model memorizes instead of learning. |
| Too many screens first | RL exploration becomes impossible. |
| Hidden state not persisted | Reward cannot be read after episode. |
| Non-debuggable APK | `run-as` may fail for SharedPreferences reads. |
| Random UI on startup | Benchmark becomes noisy. |

## 19. Minimum Checklist

Before using a dummy APK for RL, confirm:

```text
[ ] Package name is stable.
[ ] MainActivity launches with adb am start.
[ ] All important widgets have resource IDs.
[ ] App starts from clean empty state after pm clear.
[ ] Final task state is saved to SharedPreferences.
[ ] Reward can be computed from durable state.
[ ] UIAutomator can see the important widgets.
[ ] Invalid submissions do not produce success state.
[ ] Task has at least a few variants.
[ ] Benchmark saves trajectories, screenshots, video, and metrics.
```

## 20. Best Mental Model

Design dummy APKs as RL test fixtures, not product demos.

The app should be:

```text
deterministic enough to grade
realistic enough to teach useful Android behavior
simple enough for exploration
structured enough for benchmarking
```

For every new app, define these first:

```text
1. Goal
2. UI resource IDs
3. Expected durable state
4. Reward components
5. Valid action sequence
6. Failure cases
7. Benchmark variants
```

If those seven pieces are clean, the app will be usable for RL training.
