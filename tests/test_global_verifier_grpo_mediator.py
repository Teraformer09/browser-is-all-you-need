from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from Reward_GRPO import global_verifier_grpo_mediator as mediator

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "Reward_GRPO/global_verifiers_set2/task_bundle_example"


def registry() -> mediator.TaskBundleRegistry:
    return mediator.TaskBundleRegistry(
        ROOT / "Reward_GRPO/global_verifier_task_registry.json"
    )


def valid_response(expression: str = "left + right") -> str:
    return (
        "adder.h\n```cpp\n#pragma once\n"
        f"inline int add(int left, int right) {{ return {expression}; }}\n```\n"
    )


def prepared_row() -> dict:
    return mediator.prepare_dataset_row(
        {"sample_id": "adder-1", "task_bundle_id": "portable-adder"}, registry()
    )


def test_registry_authenticates_identity_and_digests() -> None:
    binding = registry().resolve("portable-adder")
    assert binding.path == EXAMPLE.resolve()
    assert binding.manifest["task_id"] == "portable-adder"
    assert len(binding.bundle_sha256) == len(binding.manifest_sha256) == 64


def test_prompt_is_public_only_and_bound_to_bundle() -> None:
    row = prepared_row()
    prompt = row["messages"][0]["content"]
    metadata = row["metadata"]
    assert "Portable Adder" in prompt
    assert '"name": "add"' in prompt
    assert "adder.h" in prompt
    assert "official_tests.cpp" not in prompt
    assert "protected_asset_hashes.json" not in prompt
    assert "tests_passed" not in prompt
    assert metadata["task_bundle_id"] == "portable-adder"
    assert metadata["prompt_sha256"] == mediator._sha256_bytes(prompt.encode())


def test_registry_rejects_bundle_tampering(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(EXAMPLE, bundle)
    payload = {
        "schema_version": 1,
        "bundles": {
            "portable-adder": {
                "path": "bundle",
                "bundle_sha256": "0" * 64,
            }
        },
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(mediator.MediatorError) as raised:
        mediator.TaskBundleRegistry(path).resolve("portable-adder")
    assert raised.value.reason == "BUNDLE_HASH_MISMATCH"


def test_host_evaluation_passes_and_preserves_reward_components() -> None:
    binding = registry().resolve("portable-adder")
    receipt = mediator.evaluate_response(
        binding, valid_response(), executor="host", invalid_retries=0
    )
    reward = mediator.receipt_to_reward(receipt)
    assert receipt["status"] == "PASS"
    assert receipt["mediator_attempts"] == 1
    assert reward == {
        "valid": True,
        "retry": False,
        "reward": 1.0,
        "correctness": 1.0,
        "format": 1.0,
        "build": 1.0,
        "api": 1.0,
        "tests": 1.0,
    }


def test_logic_failure_is_model_fail_not_infrastructure_invalid() -> None:
    binding = registry().resolve("portable-adder")
    receipt = mediator.evaluate_response(
        binding, valid_response("left - right"), executor="host", invalid_retries=0
    )
    reward = mediator.receipt_to_reward(receipt)
    assert receipt["status"] == "FAIL"
    assert reward["valid"] is True
    assert reward["build"] == reward["api"] == 1.0
    assert reward["correctness"] == 0.0
    assert reward["tests"] == pytest.approx(1 / 3)


def test_truncation_is_distinct_format_failure() -> None:
    binding = registry().resolve("portable-adder")
    receipt = mediator.evaluate_response(
        binding, "adder.h\n```cpp\nunfinished", finish_reason="length",
        executor="host", invalid_retries=0,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "TRUNCATED"
    assert receipt["format_valid"] is False


def test_reward_hook_requires_exact_prompt_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    row = prepared_row()
    sample = {"metadata": row["metadata"], "response": valid_response()}
    monkeypatch.setenv(mediator.EXECUTOR_ENV, "host")
    monkeypatch.setenv(mediator.RETRIES_ENV, "0")
    result = asyncio.run(mediator.reward_func(None, sample))
    assert result["reward"] == 1.0
    assert result["infrastructure_error"] is False

    sample["metadata"] = {**sample["metadata"], "prompt_sha256": "0" * 64}
    result = asyncio.run(mediator.reward_func(None, sample))
    assert result["reward"] == 0.0
    assert result["infrastructure_error"] is True
    assert result["reason"] == "PROMPT_BINDING_MISMATCH"
