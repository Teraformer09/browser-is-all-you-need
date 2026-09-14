"""Prime-hosted model loop + Prime VM Android worker, never a local eval upload."""
import asyncio
import json
import os
import re
import time

import verifiers as vf
from datasets import Dataset

from amazon_improved_task_001.harness.peach_episode import SYSTEM_PROMPT
from amazon_improved_task_001.harness.emulator_config import runtime_options
from amazon_improved_task_001.integrations.hosted_session import HostedSession, invalid
from amazon_improved_task_001.integrations.prime_env import episode_reward
from amazon_improved_task_001.verification.peach import task_spec
from amazon_improved_task_001.integrations.viewer_tunnel import start_viewer, stop_viewer


async def blocking(function, *args):
    """Let SDK work settle before cancellation cleanup (avoid orphaned creates)."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        except Exception:
            pass
        raise


class HostedAmazonCartEnv(vf.MultiTurnEnv):
    def __init__(self, allow_eval=False, sandbox_image="ubuntu:24.04",
                 artifact_dir="artifacts/amazon_improved_task_001_hosted", live_viewer=True, public_viewer=False,
                 rubric_profile="peach_action_budget_v1", max_attempts=12, acceleration="software", bootstrap_runtime=True, **kwargs):
        if rubric_profile not in {"legacy_v1", "peach_strict_v1", "peach_action_budget_v1"}:
            raise ValueError("Unknown rubric profile")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 12:
            raise ValueError("This setup permits at most twelve attempts")
        if type(public_viewer) is not bool or (public_viewer and live_viewer is not True):
            raise ValueError("public_viewer requires live_viewer=true and a boolean setting")
        self.bootstrap_runtime = bootstrap_runtime is True
        self.acceleration = runtime_options(acceleration)["acceleration"]
        self.public_viewer = public_viewer
        self.rubric_profile, self.max_attempts, self.attempt_count = rubric_profile, max_attempts, 0
        self.allow_eval = allow_eval is True
        self.image, self.output, self.active = sandbox_image, artifact_dir, {}
        self.task = task_spec()
        self.live_viewer, self.viewers = live_viewer is True, {}
        for key in ("max_turns", "max_examples", "env_id", "max_workers", "timeout_seconds"):
            kwargs.pop(key, None)
        dataset = Dataset.from_list([{"question": self.task["goal"], "answer": json.dumps(self.task)}])
        # MultiTurnEnv checks its turn limit before dispatching the last reply.
        # One extra model-turn slot lets the worker execute all 18 allowed actions;
        # worker termination prevents an actual nineteenth model call.
        super().__init__(dataset=dataset, eval_dataset=dataset, max_turns=self.task["max_steps"] + 1,
            timeout_seconds=runtime_options(self.acceleration)["episode_timeout_seconds"], env_id="amazon-improved-task-001", max_workers=1,
            system_prompt=SYSTEM_PROMPT, rubric=vf.Rubric(funcs=[episode_reward], weights=[1.0]), **kwargs)

    async def setup_state(self, state):
        if not self.allow_eval:
            raise RuntimeError("Explicit allow_eval=true required; this creates a billed Prime VM")
        if self.live_viewer and not self.public_viewer and re.fullmatch(r"[A-Za-z0-9_-]{43,128}", os.environ.get("DEMOCART_VIEWER_TOKEN", "")) is None:
            raise RuntimeError("Set the DEMOCART_VIEWER_TOKEN environment secret before a live hosted evaluation")
        if self.active:
            raise RuntimeError("This environment permits only one concurrent rollout")
        if self.attempt_count >= self.max_attempts:
            raise RuntimeError("Frozen campaign attempt budget exhausted; no automatic replacements")
        self.attempt_count += 1
        session = HostedSession(self.output, self.image, rubric_profile=self.rubric_profile,
                                attempt_id=str(state["trajectory_id"]), acceleration=self.acceleration, bootstrap_runtime=self.bootstrap_runtime)
        from amazon_improved_task_001.verification.strict import rubric_identity
        import hashlib
        from amazon_improved_task_001.verification.peach import TASK_PATH
        from amazon_improved_task_001.verification.action_budget import identity as budget_identity
        session.info.update(rubric=budget_identity() if self.rubric_profile == "peach_action_budget_v1" else
                            rubric_identity() if self.rubric_profile == "peach_strict_v1" else {"id":"legacy_v1"},
                            task_sha256=hashlib.sha256(TASK_PATH.read_bytes()).hexdigest())
        self.active[str(state["trajectory_id"])] = session
        state.update(android_done=False, info=session.info)
        try:
            result = await blocking(session.start)
            session.info["episode_id"] = result["episode_id"]
            state["prompt"] = [*state["prompt"], result["message"]]
            if self.live_viewer:
                self.viewers[str(state["trajectory_id"])] = await start_viewer(session, interactive=False, public_readonly=self.public_viewer)
                print("DEMOCART_LIVE_VIEWER " + json.dumps(session.info["live_viewer"]), flush=True)
        except Exception as exc:
            state["hosted_error"] = type(exc).__name__ + ": " + str(exc)
            await self.close_viewer(state)
            state["episode_verdict"] = await blocking(session.finish, state["hosted_error"])
            state["android_done"] = True
        return state

    async def get_model_response(self, state, prompt, **kwargs):
        if self.rubric_profile != "peach_action_budget_v1":
            return await super().get_model_response(state, prompt, **kwargs)
        session = self.active[str(state["trajectory_id"])]
        client = kwargs.get("client") or state["client"]
        # Observe the established transport without changing its retry or timeout policy.
        # The capped campaign owns its existing zero-retry enforcement.
        retries = getattr(getattr(client, "client", None), "max_retries", None)
        fully_measured = type(retries) is int and retries == 0
        receipts = session.info.setdefault("model_evidence_requests", [])
        receipt = {"request_index": len(receipts) + 1, "action_step": None, "raw_response": None,
                   "completion_tokens": None, "transport_retries": 0 if fully_measured else None,
                   "measurement_complete": fully_measured}
        start = time.monotonic()
        try:
            response = await super().get_model_response(state, prompt, **kwargs)
            receipt.update(response_id=getattr(response, "id", None), model=getattr(response, "model", None),
                           completion_tokens=getattr(getattr(response, "usage", None), "completion_tokens", None)
                           if fully_measured else None)
            return response
        finally:
            receipt["elapsed_seconds"] = time.monotonic() - start if fully_measured else None
            if not fully_measured:
                receipt["measurement_error"] = "OPAQUE_TRANSPORT_RETRIES"
            receipts.append(receipt)
            session.persist()

    async def env_response(self, messages, state, **kwargs):
        session = self.active[str(state["trajectory_id"])]
        reply = next((m for m in reversed(messages) if m["role"] == "assistant"), {})
        content = reply.get("content", "")
        if isinstance(content, list):
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        if self.rubric_profile == "peach_action_budget_v1":
            receipts = session.info.get("model_evidence_requests", [])
            if receipts:
                receipts[-1].update(raw_response=content,
                    action_step=1 + sum(r.get("action_step") is not None for r in receipts[:-1]))
        try:
            result = await blocking(session.call, "step", content)
            session.info["episode_id"] = result["episode_id"]
            state["android_done"] = result["done"]
            response = [result["message"]]
            if result["done"]:
                await self.close_viewer(state)
                state["episode_verdict"] = await blocking(session.finish, state.get("hosted_error"))
                state["final_env_response"] = response
            return response
        except Exception as exc:
            state["hosted_error"] = type(exc).__name__ + ": " + str(exc)
            await self.close_viewer(state)
            state["episode_verdict"] = await blocking(session.finish, state["hosted_error"])
            state["android_done"] = True
            response = [{"role": "user", "content": "Android evidence pipeline stopped; this rollout is INVALID."}]
            state["final_env_response"] = response
            return response

    @vf.stop(priority=60)
    async def cart_stopped(self, state, **kwargs):
        return bool(state.get("android_done"))

    async def close_viewer(self, state):
        viewer = self.viewers.pop(str(state.get("trajectory_id", "")), None)
        try:
            await stop_viewer(viewer)
        except Exception as exc:
            state["hosted_error"] = "LIVE_VIEWER_CLEANUP_FAILED: " + str(exc)

    @vf.cleanup
    async def close_episode(self, state):
        await self.close_viewer(state)
        session = self.active.pop(str(state.get("trajectory_id", "")), None)
        if session:
            error = state.get("hosted_error") or state.get("error")
            state["episode_verdict"] = await blocking(session.finish, error)
            state["info"] = session.info
        elif "episode_verdict" not in state:
            state["episode_verdict"] = invalid("HOSTED_SESSION_MISSING")
