import unittest

from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.tasks.ride_booking import RideBookingTask


class EpisodeSafeRewardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = DummyApkFormSearchTask(episode_id="ep_current")

    def prefs(self, **overrides: object) -> str:
        state = {
            "episode_id": "ep_current",
            "query": "airport ride",
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "submitted": "true",
            "screen": "submitted",
        }
        state.update(overrides)
        return f"""<map>
<string name="episode_id">{state["episode_id"]}</string>
<boolean name="submitted" value="{state["submitted"]}" />
<string name="query">{state["query"]}</string>
<string name="name">{state["name"]}</string>
<string name="email">{state["email"]}</string>
<string name="screen">{state["screen"]}</string>
</map>"""

    def test_reward_zero_after_reset(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(""), 0.0)

    def test_reward_rejects_old_episode_id(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(self.prefs(episode_id="ep_old")), 0.0)

    def test_reward_rejects_wrong_query(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(self.prefs(query="wrong")), 0.0)

    def test_reward_rejects_wrong_name(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(self.prefs(name="Wrong")), 0.0)

    def test_reward_rejects_wrong_email(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(self.prefs(email="wrong@example.com")), 0.0)

    def test_reward_rejects_unsubmitted_state(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(self.prefs(submitted="false")), 0.0)

    def test_reward_accepts_exact_state(self) -> None:
        self.assertEqual(self.task.reward_from_prefs(self.prefs()), 1.0)

    def test_pm_clear_clears_reward_state(self) -> None:
        components = self.task.reward_components_from_prefs("")
        self.assertFalse(any(components.values()))
        self.assertEqual(self.task.reward_from_prefs(""), 0.0)

    def test_reward_components_expose_benchmark_schema(self) -> None:
        components = self.task.reward_components_from_prefs(self.prefs())
        for key in [
            "episode_match",
            "screen_match",
            "query_match",
            "name_match",
            "email_match",
            "submitted",
            "no_forbidden_action",
            "no_invalid_action",
            "finish_after_success",
        ]:
            self.assertIn(key, components)

    def test_shaped_reward_uses_component_weights(self) -> None:
        full = self.task.shaped_reward_from_prefs(self.prefs())
        partial = self.task.shaped_reward_from_prefs(self.prefs(email="wrong@example.com"))
        self.assertEqual(full, 1.0)
        self.assertGreater(partial, 0.0)
        self.assertLess(partial, 1.0)


class RideRewardGranularityTest(unittest.TestCase):
    def test_ride_task_returns_fractional_reward_for_partial_progress(self) -> None:
        task = RideBookingTask(episode_id="ride_ep")
        prefs = """<map>
<string name="episode_id">ride_ep</string>
<string name="ride_pickup">Current location</string>
<string name="ride_type">Ride</string>
<string name="ride_drop">Noida City Centre</string>
<string name="selected_ride">Mini</string>
<string name="payment">upi</string>
<int name="journey_stage" value="2" />
<boolean name="sequence_error" value="false" />
<boolean name="ride_confirmed" value="false" />
<string name="screen">destination</string>
</map>"""
        shaped = task.shaped_reward_from_prefs(prefs)
        exact = task.reward_from_prefs(prefs)
        self.assertGreater(shaped, 0.0)
        self.assertLess(shaped, 1.0)
        self.assertEqual(exact, 0.0)

    def test_ride_task_uses_selected_fields_for_exact_success(self) -> None:
        task = RideBookingTask(episode_id="ride_ep")
        prefs = """<map>
<string name="episode_id">ride_ep</string>
<string name="ride_pickup">Current location</string>
<string name="ride_type">Ride</string>
<string name="ride_drop">Noida City Centre</string>
<string name="selected_ride">Mini</string>
<string name="payment">upi</string>
<int name="journey_stage" value="5" />
<boolean name="sequence_error" value="false" />
<boolean name="ride_confirmed" value="true" />
<string name="screen">ride_booked</string>
</map>"""
        shaped = task.shaped_reward_from_prefs(prefs)
        exact = task.reward_from_prefs(prefs)
        self.assertEqual(shaped, 1.0)
        self.assertEqual(exact, 1.0)


if __name__ == "__main__":
    unittest.main()
