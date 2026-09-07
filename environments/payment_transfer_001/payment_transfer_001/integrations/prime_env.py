"""Prime adapter: the same payment episode and signed rubric as the local runner."""
import os
import json
import verifiers as vf
from datasets import Dataset
from payment_transfer_001.harness.episode import Episode
from payment_transfer_001.harness.prompts import SYSTEM_PROMPT
from payment_transfer_001.specs import task_path
from payment_transfer_001.verification.scoring import REWARDS

def episode_reward(state, **kwargs):
    verdict = state.get("episode_verdict")
    if not isinstance(verdict,dict) or verdict.get("status") not in REWARDS or type(verdict.get("reward")) not in (int,float) or verdict["reward"] != REWARDS[verdict["status"]]:
        verdict = {"status":"INVALID","reward":0,"training_eligible":False,"reason_codes":["MISSING_OR_INCONSISTENT_VERDICT"]}
        state["episode_verdict"] = verdict
        state.setdefault("info",{})["episode_verdict"] = verdict
    return float(verdict["reward"])

class PaymentTransfer001Env(vf.MultiTurnEnv):
    def __init__(self, allow_eval=False, adb_serial=None, adb_path=None, apk_path=None,
                 artifact_dir="artifacts/payment_transfer_001", **kwargs):
        self.allow_eval, self.apk = allow_eval is True, apk_path
        self.serial, self.adb = adb_serial or os.environ.get("ADB_SERIAL"), adb_path or os.environ.get("ADB_PATH","adb")
        self.output, self.active = artifact_dir, {}
        self.task = json.loads(task_path().read_text())
        for key in ("max_turns","max_examples","env_id","max_workers"):
            kwargs.pop(key,None)
        dataset = Dataset.from_list([{"question":self.task["goal"],"answer":json.dumps(self.task["expected"])}])
        super().__init__(dataset=dataset,eval_dataset=dataset,max_turns=self.task["max_steps"],
                         env_id="payment-transfer-001",max_workers=1,system_prompt=SYSTEM_PROMPT,
                         rubric=vf.Rubric(funcs=[episode_reward],weights=[1.0]),**kwargs)

    async def setup_state(self,state):
        if not self.allow_eval or not self.apk:
            raise RuntimeError("Set allow_eval=true and apk_path after preparing an explicitly selected emulator")
        if self.active:
            raise RuntimeError("Use one concurrent rollout per ADB device")
        env = Episode(self.serial,self.apk,self.output,self.adb)
        self.active[str(state["trajectory_id"])] = env
        env.reset()
        state.update(android_done=bool(env.error),info={"artifacts":str(env.root)})
        state["prompt"] = [*state["prompt"],env.message()]
        if env.error:
            state["episode_verdict"] = env.finalize()
        return state

    async def env_response(self,messages,state,**kwargs):
        env = self.active[str(state["trajectory_id"])]
        reply = next(m for m in reversed(messages) if m["role"]=="assistant")
        content = reply.get("content","")
        if isinstance(content,list):
            content = " ".join(p.get("text","") for p in content if isinstance(p,dict))
        env.step(content)
        state["android_done"] = env.done
        state["info"]["reward_timeline"] = env.history
        response = [env.message()]
        if env.done:
            state["episode_verdict"] = env.finalize()
            state["info"]["episode_verdict"] = state["episode_verdict"]
            state["final_env_response"] = response
        return response

    @vf.stop(priority=60)
    async def payment_stopped(self,state,**kwargs):
        return bool(state.get("android_done"))

    @vf.cleanup
    async def close_episode(self,state):
        env = self.active.pop(str(state.get("trajectory_id","")),None)
        if env:
            if state.get("error"):
                env.error = str(state["error"])
            state["episode_verdict"] = env.finalize()
            state.setdefault("info",{})["episode_verdict"] = state["episode_verdict"]

def load_environment(**kwargs):
    return PaymentTransfer001Env(**kwargs)
