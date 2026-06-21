import unittest
from dataclasses import dataclass

from android_adk_rl_env.android_world_bridge import AndroidWorldDummyApkEnv, android_world_status
from android_adk_rl_env.apk_env import ApkAction
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask
from android_adk_rl_env.training.rollout import run_rollouts
from android_adk_rl_env.policies.scripted_policy import ScriptedApkPolicy


@dataclass
class MockBox:
    x_min: int
    y_min: int
    x_max: int
    y_max: int


@dataclass
class MockElement:
    resource_id: str
    text: str = ""
    resource_name: str | None = None
    class_name: str = "android.view.View"
    content_description: str = ""
    is_focused: bool = False
    is_clickable: bool = True
    is_editable: bool = False
    bbox_pixels: MockBox | None = None


@dataclass
class MockState:
    ui_elements: list[MockElement]


@dataclass
class MockJsonAction:
    action_type: str
    index: int | None = None
    text: str | None = None
    clear_text: bool | None = None
    goal_status: str | None = None


class MockJsonActionModule:
    CLICK = "click"
    INPUT_TEXT = "input_text"
    NAVIGATE_BACK = "navigate_back"
    WAIT = "wait"
    STATUS = "status"
    JSONAction = MockJsonAction


class MockAndroidWorldEnv:
    def __init__(self, task: DummyApkFormSearchTask) -> None:
        self.task = task
        self.executed = []
        self.elements = [
            MockElement(f"{task.package}:id/search_input", is_editable=True, bbox_pixels=MockBox(0, 0, 100, 100)),
            MockElement(f"{task.package}:id/search_button", text="Search", bbox_pixels=MockBox(0, 100, 100, 200)),
            MockElement(f"{task.package}:id/search_result", text="Search result: none"),
            MockElement(f"{task.package}:id/name_input", is_editable=True),
            MockElement(f"{task.package}:id/email_input", is_editable=True),
            MockElement(f"{task.package}:id/submit_button", text="Submit Form"),
            MockElement(f"{task.package}:id/status_text", text="Status: waiting"),
        ]

    def reset(self, go_home: bool = False) -> MockState:
        del go_home
        return self.get_state()

    def get_state(self, wait_to_stabilize: bool = False) -> MockState:
        del wait_to_stabilize
        return MockState(self.elements)

    def execute_action(self, action: MockJsonAction) -> None:
        self.executed.append(action)

    def close(self) -> None:
        pass


class MockAdbDevice:
    def __init__(self, task: DummyApkFormSearchTask) -> None:
        self.task = task
        self.episode_id = ""
        self.query = ""
        self.name = ""
        self.email = ""
        self.submitted = False

    def wait_for_device(self) -> None:
        pass

    def clear_app_data(self) -> None:
        self.episode_id = ""
        self.query = ""
        self.name = ""
        self.email = ""
        self.submitted = False

    def launch_app(self, episode_id: str | None = None) -> None:
        self.episode_id = episode_id or self.episode_id

    def reset_app(self, episode_id: str | None = None, extras: dict[str, object] | None = None) -> None:
        del extras
        self.clear_app_data()
        self.launch_app(episode_id=episode_id)

    def snapshot_exists(self, snapshot_name: str) -> bool:
        del snapshot_name
        return False

    def save_snapshot(self, snapshot_name: str) -> None:
        del snapshot_name

    def restore_snapshot(self, snapshot_name: str) -> None:
        del snapshot_name

    def read_shared_prefs(self) -> str:
        submitted = "true" if self.submitted else "false"
        return (
            "<map>\n"
            f"<string name=\"episode_id\">{self.episode_id}</string>\n"
            f"<boolean name=\"submitted\" value=\"{submitted}\" />\n"
            f"<string name=\"query\">{self.query}</string>\n"
            f"<string name=\"name\">{self.name}</string>\n"
            f"<string name=\"email\">{self.email}</string>\n"
            f"<string name=\"screen\">{'submitted' if self.submitted else 'form'}</string>\n"
            "</map>\n"
        )



class TestAndroidWorldBridge(unittest.TestCase):
    def make_env(self) -> AndroidWorldDummyApkEnv:
        task = DummyApkFormSearchTask(max_steps=8)
        android_env = MockAndroidWorldEnv(task)
        adb = MockAdbDevice(task)
        env = AndroidWorldDummyApkEnv(android_env=android_env, task=task, adb_device=adb, max_steps=8)
        env._json_action_module = lambda: MockJsonActionModule  # type: ignore[method-assign]
        return env

    def test_status_reports_missing_android_world_locally(self) -> None:
        status = android_world_status()
        self.assertIsInstance(status.installed, bool)

    def test_bridge_maps_resource_to_android_world_json_action(self) -> None:
        env = self.make_env()
        env.reset()

        result = env.step(ApkAction("input_resource", target="search_input", text="airport ride"))

        self.assertEqual(result.info["backend"], "android_world")
        executed = env.android_env.executed[-1]
        self.assertEqual(executed.action_type, "input_text")
        self.assertEqual(executed.index, 0)
        self.assertEqual(executed.text, "airport ride")

    def test_bridge_reports_missing_resource(self) -> None:
        env = self.make_env()
        env.reset()

        result = env.step(ApkAction("click_resource", target="missing"))

        self.assertTrue(result.info["invalid_action"])
        self.assertIn("unsupported target", result.info["error"])

    def test_bridge_rollout_uses_android_world_backend(self) -> None:
        task = DummyApkFormSearchTask(max_steps=2)

        def env_factory() -> AndroidWorldDummyApkEnv:
            android_env = MockAndroidWorldEnv(task)
            adb = MockAdbDevice(task)
            env = AndroidWorldDummyApkEnv(android_env=android_env, task=task, adb_device=adb, max_steps=2)
            env._json_action_module = lambda: MockJsonActionModule  # type: ignore[method-assign]
            return env

        rollouts = run_rollouts(env_factory, lambda: ScriptedApkPolicy(task), episodes=1)

        self.assertEqual(rollouts[0]["final_observation"]["backend"], "android_world")
        self.assertEqual(rollouts[0]["steps"], 2)

    def test_observation_schema_is_standardized(self) -> None:
        env = self.make_env()
        observation = env.reset()

        self.assertEqual(observation["schema_version"], "mobile_observation.v1")
        self.assertEqual(observation["backend"], "android_world")
        self.assertIn("ui", observation)


if __name__ == "__main__":
    unittest.main()
