"""Prime adapter: the same single-task harness and stage score as local runs."""
from __future__ import annotations

import json
import os

import verifiers as vf
from datasets import Dataset
from uber_clone_031.harness.backend.task_specs import build_known_task, load_task_spec

from uber_clone_031.harness.evidence import EvidenceEnv
from uber_clone_031.harness.episode import RideStageEnv
from uber_clone_031.harness.device import TracedAdbDevice
from uber_clone_031.harness.prompts import SYSTEM_PROMPT
from uber_clone_031.cli import observation_message, task_path, parse_action


def episode_reward(state, **kwargs):
    verdict = state.get("episode_verdict")
    if not isinstance(verdict, dict) or verdict.get("status") not in {"PASS", "FAIL", "INVALID"}:
        verdict = {"status": "INVALID", "reward": 0, "training_eligible": False,
                   "reason_codes": ["MISSING_EPISODE_VERDICT"]}
        state["episode_verdict"] = verdict
        state.setdefault("info", {})["episode_verdict"] = verdict
    expected = {"PASS": 1, "INVALID": 0, "FAIL": -1}[verdict["status"]]
    if type(verdict.get("reward")) not in (int, float) or verdict["reward"] != expected:
        state["episode_verdict"] = {"status": "INVALID", "reward": 0, "training_eligible": False,
                                    "reason_codes": ["INCONSISTENT_EPISODE_VERDICT"]}
        state.setdefault("info", {})["episode_verdict"] = state["episode_verdict"]
        return 0.0
    return float(verdict["reward"])


def task_success(state, **kwargs):
    return float(state.get("android_success", False))


def completed_stages(state, **kwargs):
    return float(state.get("android_observation", {}).get("scorecard", {}).get("completed_stages", 0))


class UberClone031Env(vf.MultiTurnEnv):
    def __init__(self, artifact_dir=None, backend="adb", adb_path=None, adb_serial=None, apk_path=None, allow_eval=False, **kwargs):
        if backend != "adb":
            raise ValueError("uber_clone_031 requires backend='adb'")
        self.artifact_dir = artifact_dir or os.environ.get("UBER031_ARTIFACT_DIR", "artifacts/uber_clone_031")
        self.adb_path = adb_path or os.environ.get("ADB_PATH", "adb")
        self.adb_serial = adb_serial or os.environ.get("ADB_SERIAL")
        self.task = build_known_task(load_task_spec(task_path()))
        self._envs = {}
        self.allow_eval = allow_eval is True
        self.apk_path = apk_path
        # This package always represents exactly one fixed task and one device.
        for key in ("task_path", "max_examples", "max_turns", "shaped_rewards", "wait_to_stabilize",
                    "console_port", "grpc_port", "env_id", "max_workers"):
            kwargs.pop(key, None)
        dataset = Dataset.from_list([{"question": self.task.goal, "answer": json.dumps(self.task.expected_state())}])
        super().__init__(max_turns=self.task.max_steps, dataset=dataset, eval_dataset=dataset,
                         system_prompt=SYSTEM_PROMPT, env_id="uber-clone-031", max_workers=1,
                         rubric=vf.Rubric(funcs=[episode_reward, task_success, completed_stages],
                                          weights=[1.0, 0.0, 0.0]), **kwargs)

    def _create_env(self):
        if not self.allow_eval:
            raise RuntimeError("Evaluation is disabled. Set allow_eval=true only after explicit approval.")
        if self._envs:
            raise RuntimeError("One ADB device supports one active rollout; set max_concurrent=1")
        device = TracedAdbDevice(adb_path=self.adb_path, serial=self.adb_serial, package=self.task.package)
        return EvidenceEnv(RideStageEnv(task=self.task, device=device, max_steps=self.task.max_steps), self.artifact_dir, apk_path=self.apk_path)

    async def setup_state(self, state):
        env = self._create_env()
        obs = env.reset()
        self._envs[str(state["trajectory_id"])] = env
        state.update(android_observation=obs, android_reward=obs["reward"],
                     android_success=obs["exact_success"], android_done=env.env.done,
                     android_transitions=[], info={"stage_diagnostics": obs["scorecard"], "artifacts": str(env.run_dir),
                                                   "installed_apk": env.installed_apk})
        state["prompt"] = [*state["prompt"], observation_message(env, obs)]
        return state

    @staticmethod
    def _last_assistant_text(messages):
        for message in reversed(messages):
            if message.get("role") == "assistant":
                content = message.get("content", "")
                if isinstance(content, str):
                    return content
                return " ".join(part.get("text", "") for part in (content or []) if isinstance(part, dict))
        return ""

    async def env_response(self, messages, state, **kwargs):
        env = self._envs[str(state["trajectory_id"])]
        action = parse_action(self._last_assistant_text(messages))
        result = env.step(action)
        obs, score = result.observation, result.observation["scorecard"]
        state.update(android_observation=obs, android_reward=obs["reward"],
                     android_final_reward=obs["final_reward"], android_success=obs["exact_success"],
                     episode_verdict=env.verdict,
                     android_done=result.done)
        state["android_transitions"].append({"action": action, "reward": obs.get("episode_reward"), "reward_status": obs.get("reward_status"),
                                              "progress_report": obs.get("progress_report"), "info": result.info})
        state["info"].update(stage_diagnostics=score, episode_verdict=env.verdict,
                             reward_timeline=env.progress_history, artifacts=str(env.run_dir))
        response = [observation_message(env, obs)]
        if result.done:
            state["final_env_response"] = response
        return response

    @vf.stop(priority=60)
    async def evidence_episode_done(self, state, **kwargs):
        return bool(state.get("android_done", False))

    @vf.cleanup
    async def close_android_env(self, state):
        env = self._envs.pop(str(state.get("trajectory_id", "")), None)
        if env is not None:
            verdict = env.finalize(stop_reason=str(state.get("error") or "") or None,
                                   failure_origin="pipeline" if state.get("error") else "none")
            state.update(episode_verdict=verdict, android_reward=verdict["reward"],
                         android_success=verdict["status"] == "PASS", android_observation=env.last_observation)
            state.setdefault("info", {}).update(episode_verdict=verdict, scorecard=verdict,
                                               stage_diagnostics=env.last_observation.get("scorecard"),
                                               training_eligible=verdict["training_eligible"])
            env.close()


def load_environment(**kwargs):
    return UberClone031Env(**kwargs)
