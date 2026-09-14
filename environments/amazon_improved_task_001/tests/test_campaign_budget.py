"""No inference or sandboxes: frozen campaign bounds and packaging regressions."""
import base64
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

from amazon_improved_task_001.integrations.campaign_budget import CampaignBudget, bounded_prompt
from amazon_improved_task_001.integrations.runtime_bootstrap import source_bundle
from amazon_improved_task_001.integrations.hosted_session import HostedSession
from amazon_improved_task_001 import load_environment


def message(text="Home"):
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + (1080).to_bytes(4, "big") + (2400).to_bytes(4, "big")
    return {"role": "user", "content": [
        {"type": "text", "text": json.dumps({"goal": "cart", "step": 0, "ui": [
            {"id": "search_input", "text": text, "enabled": True, "clickable": True, "bounds": [1, 2, 3, 4], "resource_id": "unused"}], "last_error": None})},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}}]}


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_complete_campaign_under_approved_cap(self):
        budget = CampaignBudget(9, self.root)
        for _ in range(12):
            budget.reserve_attempt()
            for _ in range(18):
                receipt = budget.reserve_call()
        self.assertEqual(receipt["requests_reserved"], 216)
        self.assertEqual(Decimal(str(receipt["reserved_upper_bound_usd"])), Decimal("8.866944"))
        with self.assertRaises(RuntimeError): budget.reserve_attempt()
        with self.assertRaises(RuntimeError): budget.reserve_call()

    def test_explicit_cap_and_no_duplicate_ledger(self):
        for value in (None, True, 10, 8):
            with self.assertRaises((ValueError, TypeError, ArithmeticError)):
                CampaignBudget(value, self.root)
        CampaignBudget(9, self.root)
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            CampaignBudget(9, self.root)

    def test_stopped_campaign_creates_no_more_requests(self):
        budget = CampaignBudget(9, self.root)
        with self.assertRaises(RuntimeError): budget.reserve_call()
        budget.reserve_attempt()
        budget.reserve_call()
        budget.stopped = True
        with self.assertRaises(RuntimeError): budget.reserve_call()
        with self.assertRaises(RuntimeError): budget.reserve_attempt()

    def test_only_current_original_image_and_actions(self):
        current = message()
        prompt, upper = bounded_prompt([{"role": "system", "content": "JSON actions"}, message("old"), current], ['{"type":"wait"}'])
        self.assertEqual(len(prompt), 2)
        self.assertLessEqual(upper, 8000)
        public = json.loads(prompt[-1]["content"][0]["text"])
        self.assertEqual(public["previous_actions"], ['{"type":"wait"}'])
        self.assertNotIn("resource_id", public["ui"][0])
        self.assertEqual(prompt[-1]["content"][1]["image_url"]["url"], current["content"][1]["image_url"]["url"])
        self.assertEqual(prompt[-1]["content"][1]["image_url"]["detail"], "high")

    def test_large_prompt_is_rejected_without_silent_truncation(self):
        with self.assertRaisesRegex(ValueError, "input allowance"):
            bounded_prompt([{"role": "system", "content": "JSON"}, message("large " * 8000)], [])

    def test_missing_or_unexpected_image_is_rejected(self):
        current = message()
        current["content"].pop()
        with self.assertRaisesRegex(ValueError, "screenshot"):
            bounded_prompt([{"role": "system", "content": "JSON"}, current], [])

    def test_bootstrap_is_explicit_software_only(self):
        for image, acceleration in (("ubuntu:latest", "software"), ("ubuntu:24.04", "kvm")):
            with self.assertRaises(ValueError):
                HostedSession(self.root, image, bootstrap_runtime=True, acceleration=acceleration)
        session = HostedSession(self.root, "ubuntu:24.04", bootstrap_runtime=True, acceleration="software", client=Mock())
        self.assertEqual(session.command_environment()["env"]["JAVA_HOME"], "/usr/lib/jvm/java-21-openjdk-amd64")
        self.assertEqual(session.options["sandbox_timeout_minutes"], 30)

    def test_source_bundle_contains_app_and_no_private_paths(self):
        import tarfile
        archive = self.root / "source.tar.gz"
        receipt = source_bundle(archive)
        self.assertLess(receipt["bytes"], 2_000_000)
        with tarfile.open(archive) as tar:
            names = tar.getnames()
        self.assertIn("scripts/provision_android.sh", names)
        self.assertIn("amazon_improved_task_001/integrations/capped_env.py", names)
        self.assertTrue(any(name.endswith("MainActivity.java") for name in names))
        self.assertFalse(any("artifacts/" in name or "__pycache__" in name for name in names))

    def test_loading_capped_environment_does_not_create_ledger_or_vm(self):
        with patch("amazon_improved_task_001.integrations.hosted_env.HostedSession") as session:
            env = load_environment(capped_campaign=True, max_total_spend_usd=9, artifact_dir=str(self.root))
            self.assertIsNone(env.budget)
            self.assertTrue(env.bootstrap_runtime)
            self.assertFalse(env.allow_eval)
            self.assertFalse((self.root / "campaign-budget.json").exists())
            session.assert_not_called()
        with self.assertRaises(ValueError):
            load_environment(capped_campaign=True, max_total_spend_usd=9, rubric_profile="legacy_v1")

    def test_real_client_adapter_uses_one_capped_request_without_network(self):
        import asyncio
        import httpx
        from openai import AsyncOpenAI
        from types import SimpleNamespace
        from verifiers.legacy.clients.openai_chat_completions_client import OpenAIChatCompletionsClient
        from verifiers.legacy.types import SystemMessage, UserMessage
        seen = []
        def respond(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "offline-fixture", "object": "chat.completion", "created": 1,
                "model": "gpt-4.1-2025-04-14", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"type":"wait"}'}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 8, "total_tokens": 1008}})
        async def check():
            native = AsyncOpenAI(api_key="offline-test-only", base_url="https://offline.invalid/v1",
                max_retries=10, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
            client = OpenAIChatCompletionsClient(native)
            env = load_environment(capped_campaign=True, max_total_spend_usd=9, artifact_dir=str(self.root))
            env.budget = CampaignBudget(9, self.root)
            env.budget.reserve_attempt()
            session = SimpleNamespace(info={}, persist=lambda: None)
            env.active["offline"] = session
            state = {"trajectory_id": "offline", "trajectory": [], "model": "openai/gpt-4.1", "client": client,
                     "input_token_upper_bound": 6000}
            result = await env.get_model_response(state, [SystemMessage(content="JSON"),
                UserMessage(content="Return a wait JSON action")])
            self.assertEqual(result.usage.prompt_tokens, 1000)
            self.assertEqual(client.client.max_retries, 0)
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0]["max_completion_tokens"], 2048)
            self.assertEqual(seen[0]["temperature"], 0.6)
            self.assertEqual(env.budget.calls, 1)
            self.assertFalse(env.budget.stopped)
            await client.close()
        asyncio.run(check())
