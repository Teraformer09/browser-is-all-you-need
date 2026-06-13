"""Prime Intellect / verifiers environment for the dummy Android APK."""

from __future__ import annotations

import json
from typing import Any

import verifiers as vf
from datasets import Dataset

from android_adk_rl_env.adb_device import AdbDevice
from android_adk_rl_env.android_world_bridge import create_native_android_world_env
from android_adk_rl_env.apk_env import ApkAction, DummyApkEnv
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask

SYSTEM_PROMPT = """You control a real mobile Android APK through JSON actions.
Return exactly one JSON object per turn. Do not include markdown.
Allowed actions:
{"type":"type_text","element_id":"search_input","text":"airport ride","x":null,"y":null,"x1":null,"y1":null,"x2":null,"y2":null,"duration_ms":null}
{"type":"tap_element","element_id":"search_button","text":null,"x":null,"y":null,"x1":null,"y1":null,"x2":null,"y2":null,"duration_ms":null}
{"type":"type_text","element_id":"name_input","text":"Ada Lovelace","x":null,"y":null,"x1":null,"y1":null,"x2":null,"y2":null,"duration_ms":null}
{"type":"type_text","element_id":"email_input","text":"ada@example.com","x":null,"y":null,"x1":null,"y1":null,"x2":null,"y2":null,"duration_ms":null}
{"type":"tap_element","element_id":"submit_button","text":null,"x":null,"y":null,"x1":null,"y1":null,"x2":null,"y2":null,"duration_ms":null}
{"type":"finish","element_id":null,"text":null,"x":null,"y":null,"x1":null,"y1":null,"x2":null,"y2":null,"duration_ms":null}
Use finish only after final_reward is 1.0.
Priority: fill search_input, click search_button, fill name_input, fill email_input, click submit_button, then finish.
"""


def _apk_reward(state: vf.State, **kwargs: Any) -> float:
    del kwargs
    return float(state.get("android_final_reward", 0.0) or 0.0)


class PrimeAndroidApkEnv(vf.MultiTurnEnv):
    """Prime/verifiers multi-turn environment backed by a real Android APK.

    The model emits a JSON action. The environment executes it against the dummy
    APK through either direct ADB or AndroidWorld, then returns the next
    observation. Reward is read from the APK SharedPreferences via the existing
    task reward function.
    """

    def __init__(
        self,
        backend: str = "adb",
        adb_path: str = "adb",
        adb_serial: str | None = None,
        console_port: int = 5556,
        grpc_port: int = 8554,
        max_turns: int = 15,
        max_examples: int = 1,
        shaped_rewards: bool = True,
        wait_to_stabilize: bool = False,
        **kwargs: Any,
    ) -> None:
        if backend not in {"adb", "android_world"}:
            raise ValueError("backend must be 'adb' or 'android_world'")
        self.backend = backend
        self.adb_path = adb_path
        self.adb_serial = adb_serial
        self.console_port = console_port
        self.grpc_port = grpc_port
        self.task = DummyApkFormSearchTask(max_steps=max_turns)
        self.shaped_rewards = shaped_rewards
        self.wait_to_stabilize = wait_to_stabilize
        self._envs: dict[str, Any] = {}

        rows = [
            {
                "question": self.task.goal,
                "answer": self.task.expected_state(),
            }
            for _ in range(max_examples)
        ]
        dataset = Dataset.from_list(rows)
        rubric = vf.Rubric(funcs=[_apk_reward], weights=[1.0])
        super().__init__(
            max_turns=max_turns,
            dataset=dataset,
            eval_dataset=dataset,
            system_prompt=SYSTEM_PROMPT,
            rubric=rubric,
            env_id="prime-android-apk-adk",
            max_workers=1,
            **kwargs,
        )

    async def setup_state(self, state: vf.State) -> vf.State:
        env = self._create_env()
        observation = env.reset()
        key = str(state["trajectory_id"])
        self._envs[key] = env
        state["android_observation"] = observation
        state["android_reward"] = float(observation.get("reward", 0.0) or 0.0)
        state["android_final_reward"] = float(observation.get("final_reward", 0.0) or 0.0)
        state["android_success"] = False
        state["android_transitions"] = []
        state["info"] = {
            "backend": self.backend,
            "package": self.task.package,
            "goal": self.task.goal,
        }
        state["prompt"] = [
            *state["prompt"],
            {"role": "user", "content": self._format_observation(observation)},
        ]
        return state

    async def env_response(self, messages: vf.Messages, state: vf.State, **kwargs: Any) -> vf.Messages:
        del kwargs
        key = str(state["trajectory_id"])
        env = self._envs[key]
        action, parse_error = self._parse_action(messages)
        if parse_error is not None:
            observation = state.get("android_observation", {})
            response = {
                "error": parse_error,
                "instruction": "Return one JSON action object with action, target, and text.",
                "observation": self._compact_observation(observation),
            }
            return [{"role": "user", "content": json.dumps(response, sort_keys=True)}]

        result = env.step(action)
        observation = result.observation
        final_reward = float(observation.get("final_reward", 0.0) or 0.0)
        reward = float(observation.get("reward", result.reward) or 0.0)
        transition = {
            "action": action.to_dict(),
            "reward": reward,
            "final_reward": final_reward,
            "done": bool(result.done),
            "info": result.info,
        }
        state["android_observation"] = observation
        state["android_reward"] = reward
        state["android_final_reward"] = final_reward
        state["android_success"] = final_reward >= 1.0
        state["android_transitions"].append(transition)
        state["info"] = {
            **state.get("info", {}),
            "last_transition": transition,
            "reward_components": observation.get("reward_components", {}),
        }

        content = self._format_observation(observation)
        response = [{"role": "user", "content": content}]
        if result.done:
            state["final_env_response"] = response
        return response

    @vf.stop(priority=50)
    async def android_task_completed(self, state: vf.State, **kwargs: Any) -> bool:
        del kwargs
        return bool(state.get("android_success", False))

    @vf.cleanup
    async def close_android_env(self, state: vf.State) -> None:
        key = str(state.get("trajectory_id", ""))
        env = self._envs.pop(key, None)
        if env is not None and hasattr(env, "close"):
            env.close()

    def _create_env(self) -> Any:
        if self.backend == "android_world":
            return create_native_android_world_env(
                console_port=self.console_port,
                adb_path=self.adb_path,
                adb_serial=self.adb_serial,
                grpc_port=self.grpc_port,
                task=self.task,
                max_steps=self.max_turns,
                shaped_rewards=self.shaped_rewards,
                wait_to_stabilize=self.wait_to_stabilize,
            )
        return DummyApkEnv(
            task=self.task,
            device=AdbDevice(adb_path=self.adb_path, package=self.task.package, serial=self.adb_serial),
            max_steps=self.max_turns,
            shaped_rewards=self.shaped_rewards,
        )

    def _parse_action(self, messages: vf.Messages) -> tuple[ApkAction, str | None]:
        text = self._last_assistant_text(messages)
        if not text:
            return ApkAction("wait"), "missing assistant action"
        try:
            raw = json.loads(self._strip_code_fence(text))
        except json.JSONDecodeError as exc:
            return ApkAction("wait"), f"invalid JSON action: {exc}"
        try:
            return ApkAction.from_dict(raw), None
        except Exception as exc:  # noqa: BLE001
            return ApkAction("wait"), f"invalid action object: {type(exc).__name__}: {exc}"

    def _last_assistant_text(self, messages: vf.Messages) -> str:
        for message in reversed(messages):
            role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
            if role != "assistant":
                continue
            content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                chunks = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        chunks.append(part["text"])
                    elif isinstance(getattr(part, "text", None), str):
                        chunks.append(part.text)
                return " ".join(chunks).strip()
        return ""

    def _strip_code_fence(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return stripped

    def _format_observation(self, observation: dict[str, Any]) -> str:
        return json.dumps(self._compact_observation(observation), sort_keys=True)

    def _compact_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        reward_components = observation.get("reward_components") or {}
        ui = observation.get("ui") or []
        return {
            "goal": observation.get("goal"),
            "backend": observation.get("backend", self.backend),
            "steps": observation.get("steps"),
            "max_steps": observation.get("max_steps"),
            "reward": observation.get("reward"),
            "final_reward": observation.get("final_reward"),
            "reward_components": reward_components,
            "missing_reward_components": [name for name, passed in reward_components.items() if not passed],
            "valid_targets": [node.get("id") for node in ui if node.get("id")],
            "ui": ui,
            "last_action": observation.get("last_action"),
            "last_error": observation.get("last_error"),
            "expected_state": observation.get("expected_state"),
        }


def load_environment(**kwargs: Any) -> vf.Environment:
    """Prime CLI entry point."""
    return PrimeAndroidApkEnv(**kwargs)
