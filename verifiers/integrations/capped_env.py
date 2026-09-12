"""Twelve hosted attempts with frozen sampling, media context and monetary guards."""
import json

import verifiers as vf

from amazon_cart_001.integrations.hosted_env import HostedAmazonCartEnv
from amazon_cart_001.integrations.campaign_budget import (CampaignBudget, campaign_plan, bounded_prompt,
    as_dict, valid_model, INPUT_LIMIT, OUTPUT_LIMIT, DEFAULT_MODEL, DEFAULT_INPUT_USD, DEFAULT_OUTPUT_USD)


class CappedHostedAmazonCartEnv(HostedAmazonCartEnv):
    def __init__(self, max_total_spend_usd=None, completed_attempts=0,
                 attempts_this_run=None, prior_spend_usd=0, campaign_model=DEFAULT_MODEL,
                 campaign_input_usd=DEFAULT_INPUT_USD, campaign_output_usd=DEFAULT_OUTPUT_USD,
                 planned_attempts=12, campaign_temperature=0.6, **kwargs):
        if type(max_total_spend_usd) not in (int, float):
            raise ValueError("Explicit max_total_spend_usd required")
        if type(campaign_temperature) not in (int, float) or isinstance(campaign_temperature, bool) \
                or not 0 <= campaign_temperature <= 1:
            raise ValueError("campaign_temperature must be a number from 0 through 1")
        plan = campaign_plan(max_total_spend_usd, completed_attempts, attempts_this_run, prior_spend_usd,
                             input_usd=campaign_input_usd, output_usd=campaign_output_usd,
                             planned_attempts=planned_attempts)
        self.completed_attempts, self.run_attempt_limit = plan["completed_attempts"], plan["attempt_limit"]
        self.prior_spend_usd = plan["prior_spend"]
        self.campaign_model = valid_model(campaign_model)
        self.campaign_prices = (campaign_input_usd, campaign_output_usd)
        self.planned_attempts = planned_attempts
        self.campaign_temperature = campaign_temperature
        for key, required in {"sandbox_image": "ubuntu:24.04", "acceleration": "software",
                              "bootstrap_runtime": True, "public_viewer": True, "live_viewer": True,
                              "max_attempts": self.run_attempt_limit, "rubric_profile": "peach_strict_v1"}.items():
            if key in kwargs and kwargs[key] != required:
                raise ValueError("Frozen campaign setting differs: " + key)
            kwargs[key] = required
        super().__init__(**kwargs)
        self.budget = None
        self.approved_cap = max_total_spend_usd

    async def setup_state(self, state):
        if not self.allow_eval:
            return await super().setup_state(state)
        if self.budget is None:
            self.budget = CampaignBudget(self.approved_cap, self.output,
                completed_attempts=self.completed_attempts, attempts_this_run=self.run_attempt_limit,
                prior_spend_usd=self.prior_spend_usd, input_usd=self.campaign_prices[0],
                output_usd=self.campaign_prices[1], planned_attempts=self.planned_attempts,
                model=self.campaign_model)
        try:
            self.budget.reserve_attempt()
        except RuntimeError as exc:
            raise vf.Error(str(exc)) from exc
        result = await super().setup_state(state)
        state["info"]["campaign_budget"] = self.budget.persist()
        state["info"]["campaign_attempt_number"] = self.completed_attempts + self.budget.attempts
        state["info"]["campaign_planned_attempts"] = self.planned_attempts
        if state.get("hosted_error"):
            self.budget.stopped = True
            self.budget.persist()
        return result

    async def get_prompt_messages(self, state):
        messages = await super().get_prompt_messages(state)
        if state.get("final_env_response") is not None:
            return messages
        actions = []
        for step in state["trajectory"]:
            for message in step["completion"]:
                value = as_dict(message)
                if value["role"] == "assistant":
                    actions.append(value.get("content", ""))
        try:
            prompt, upper = bounded_prompt(messages, actions)
        except Exception as exc:
            state["hosted_error"] = "CAMPAIGN_CONTEXT_GUARD: " + str(exc)
            raise vf.Error(state["hosted_error"]) from exc
        state["input_token_upper_bound"] = upper
        return prompt

    async def render_completion(self, state):
        # The actor sees a sliding observation window, but the dashboard retains
        # every actual request image and reply rather than only the final window.
        trajectory = state["trajectory"]
        if not trajectory:
            state["completion"] = []
            return
        state["prompt"] = trajectory[0]["prompt"]
        completion = list(trajectory[0]["completion"])
        for step in trajectory[1:]:
            completion.append(step["prompt"][-1])
            completion.extend(step["completion"])
        completion.extend(state.get("final_env_response") or [])
        state["completion"] = completion

    async def get_model_response(self, state, prompt, **kwargs):
        client = state["client"]
        if state["model"] != self.campaign_model or type(client).__name__ != "OpenAIChatCompletionsClient":
            raise vf.Error("Frozen campaign requires the declared Prime chat-completions model")
        if len(state["trajectory"]) >= 18:
            raise vf.Error("Eighteen model requests per attempt maximum")
        # Use the framework's credentialed client, but never its ten-retry default.
        client._client = client.client.with_options(max_retries=0, timeout=120)
        if client.client.max_retries != 0:
            raise vf.Error("Could not enforce zero inference retries")
        try:
            self.budget.reserve_call()
        except RuntimeError as exc:
            raise vf.Error(str(exc)) from exc
        session = self.active[str(state["trajectory_id"])]
        receipt = {"request_index": len(state["trajectory"]) + 1,
                   "campaign_attempt_number": self.completed_attempts + self.budget.attempts,
                   "campaign_model": self.campaign_model,
                   "input_token_upper_bound": state["input_token_upper_bound"],
                   "max_output_tokens": OUTPUT_LIMIT, "transport_retries": 0,
                   "sampling": {"temperature": self.campaign_temperature, "response_format": {"type": "json_object"}}}
        try:
            response = await super().get_model_response(state, prompt, client=client,
                model=self.campaign_model, tool_defs=None, sampling_args={"temperature": self.campaign_temperature,
                    "max_tokens": OUTPUT_LIMIT, "response_format": {"type": "json_object"}})
            usage = response.usage
            if usage is None:
                raise vf.Error("Missing usage receipt; stopping campaign before further inference")
            receipt.update(response_id=response.id, returned_model=response.model, usage=usage.model_dump())
            if usage.prompt_tokens > INPUT_LIMIT or usage.completion_tokens > OUTPUT_LIMIT:
                raise vf.Error("Provider usage exceeded frozen reservation; stopping campaign")
            return response
        except BaseException as exc:
            self.budget.stopped = True
            state["hosted_error"] = "CAMPAIGN_INFERENCE_STOP: " + type(exc).__name__
            receipt["error_type"] = type(exc).__name__
            raise
        finally:
            session.info.setdefault("model_requests", []).append(receipt)
            session.info["campaign_budget"] = self.budget.persist()
            session.persist()
            print("DEMOCART_MODEL_REQUEST " + json.dumps(receipt), flush=True)
