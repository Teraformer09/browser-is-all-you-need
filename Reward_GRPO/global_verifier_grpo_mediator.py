"""Bind GRPO prompts and rewards to authenticated Global Verifiers Set 2 bundles.

The verifier implementation remains task-independent.  This module is the runtime
mediator: it resolves a task ID, authenticates its immutable bundle, constructs the
public Aider-style prompt, verifies prompt/bundle binding metadata, runs Set 2, and
projects its receipt into GRPO reward components.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath
from tempfile import TemporaryDirectory
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parent
SET2 = ROOT / "global_verifiers_set2"
DEFAULT_REGISTRY = ROOT / "global_verifier_task_registry.json"
REGISTRY_ENV = "GLOBAL_VERIFIER_SET2_REGISTRY"
EXECUTOR_ENV = "GLOBAL_VERIFIER_SET2_EXECUTOR"
RETRIES_ENV = "GLOBAL_VERIFIER_SET2_INVALID_RETRIES"


class MediatorError(ValueError):
    """An unauthenticated or inconsistent GRPO-to-verifier request."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _safe_relative(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise MediatorError("INVALID_REGISTRY", f"{field} must be a relative path")
    path = PurePath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise MediatorError("INVALID_REGISTRY", f"{field} is unsafe")
    return value


def bundle_tree_sha256(root: Path) -> str:
    """Hash names and bytes for every regular bundle file in stable order."""

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise MediatorError("UNSAFE_BUNDLE", f"bundle contains symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _set2_runner():
    """Load the intentionally flat ten-file Set 2 package without changing it."""

    set2_text = str(SET2)
    if set2_text not in sys.path:
        sys.path.insert(0, set2_text)
    module = importlib.import_module("runner")
    if Path(module.__file__).resolve() != (SET2 / "runner.py").resolve():
        raise MediatorError("RUNNER_IDENTITY_MISMATCH", "a different runner module was loaded")
    return module


@dataclass(frozen=True)
class BundleBinding:
    task_bundle_id: str
    path: Path
    bundle_sha256: str
    manifest_sha256: str
    contract_version: str
    manifest: dict[str, Any]


@dataclass(frozen=True)
class PromptEnvelope:
    prompt: str
    metadata: dict[str, str]


class TaskBundleRegistry:
    """Resolve allow-listed task IDs to authenticated on-disk bundles."""

    def __init__(self, registry_path: Path) -> None:
        self.path = registry_path.resolve(strict=True)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("bundles"), dict):
            raise MediatorError("INVALID_REGISTRY", "unsupported task-bundle registry")
        self._entries: dict[str, Any] = payload["bundles"]
        self._root = self.path.parent.resolve(strict=True)

    def resolve(self, task_bundle_id: str) -> BundleBinding:
        entry = self._entries.get(task_bundle_id)
        if not isinstance(entry, dict):
            raise MediatorError("UNKNOWN_TASK_BUNDLE", task_bundle_id)
        relative = _safe_relative(entry.get("path"), f"bundles.{task_bundle_id}.path")
        path = (self._root / relative).resolve(strict=True)
        if not path.is_relative_to(self._root) or not path.is_dir():
            raise MediatorError("UNSAFE_BUNDLE", task_bundle_id)
        expected_bundle = entry.get("bundle_sha256")
        if not isinstance(expected_bundle, str) or len(expected_bundle) != 64:
            raise MediatorError("INVALID_REGISTRY", "bundle_sha256 is malformed")
        actual_bundle = bundle_tree_sha256(path)
        if actual_bundle != expected_bundle:
            raise MediatorError("BUNDLE_HASH_MISMATCH", task_bundle_id)
        runner = _set2_runner()
        try:
            manifest, manifest_sha = runner.load_bundle(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise MediatorError("INVALID_TASK_BUNDLE", str(error)) from error
        if manifest["task_id"] != task_bundle_id:
            raise MediatorError("BUNDLE_IDENTITY_MISMATCH", task_bundle_id)
        expected_manifest = entry.get("manifest_sha256")
        if expected_manifest is not None and expected_manifest != manifest_sha:
            raise MediatorError("MANIFEST_HASH_MISMATCH", task_bundle_id)
        return BundleBinding(task_bundle_id, path, actual_bundle, manifest_sha,
                             str(manifest["contract_version"]), manifest)


def _public_starter_files(binding: BundleBinding) -> list[str]:
    configured = binding.manifest.get("prompt", {}).get("public_starter_files")
    if configured is None:
        configured = sorted(
            path.relative_to(binding.path / "starter").as_posix()
            for path in (binding.path / "starter").rglob("*") if path.is_file()
        )
    if not isinstance(configured, list) or not configured:
        raise MediatorError("INVALID_PROMPT_CONTRACT", "no public starter files")
    result: list[str] = []
    for index, value in enumerate(configured):
        relative = _safe_relative(value, f"public_starter_files[{index}]")
        path = binding.path / "starter" / relative
        if not path.is_file() or path.is_symlink():
            raise MediatorError("INVALID_PROMPT_CONTRACT", f"missing starter file: {relative}")
        result.append(relative)
    return result


def build_prompt(binding: BundleBinding) -> PromptEnvelope:
    """Construct a public-only Aider whole-file prompt from one authenticated bundle."""

    manifest = binding.manifest
    contract_name = str(manifest["api"]["contract"])
    instructions = (binding.path / "instructions.md").read_text(encoding="utf-8").strip()
    contract = (binding.path / contract_name).read_text(encoding="utf-8").strip()
    build = manifest.get("build", {})
    sections = [
        instructions,
        "## Public API contract\n\n```json\n" + contract + "\n```",
        "## Public build contract\n\n"
        f"C++ standard: `{build.get('standard', 'c++17')}`\n\n"
        f"Compiler flags: `{json.dumps(build.get('flags', []))}`\n\n"
        f"Libraries: `{json.dumps(build.get('libraries', []))}`",
    ]
    for name in _public_starter_files(binding):
        content = (binding.path / "starter" / name).read_text(encoding="utf-8").rstrip()
        sections.append(f"## `{name}`\n\n```cpp\n{content}\n```")
    editable = "\n".join(f"- `{name}`" for name in manifest["editable_files"])
    sections.append(
        "## Response contract\n\n"
        "Return complete contents only for files you modify, using the exact Aider format "
        "`filename` followed by a fenced C++ block. Do not return any other filename. "
        "Omitted editable files inherit their unchanged starter contents.\n\n"
        f"Editable files:\n{editable}"
    )
    prompt = "\n\n".join(sections).strip() + "\n"
    metadata = {
        "task_bundle_id": binding.task_bundle_id,
        "bundle_sha256": binding.bundle_sha256,
        "manifest_sha256": binding.manifest_sha256,
        "contract_version": binding.contract_version,
        "prompt_sha256": _sha256_bytes(prompt.encode()),
    }
    return PromptEnvelope(prompt, metadata)


def prepare_dataset_row(row: Mapping[str, Any], registry: TaskBundleRegistry) -> dict[str, Any]:
    """Return a dataset row whose user prompt and verifier binding share one source."""

    result = dict(row)
    metadata = dict(result.get("metadata") or {})
    task_bundle_id = metadata.get("task_bundle_id") or result.get("task_bundle_id")
    if not isinstance(task_bundle_id, str):
        raise MediatorError("MISSING_TASK_BUNDLE_ID", "dataset row lacks task_bundle_id")
    envelope = build_prompt(registry.resolve(task_bundle_id))
    result["messages"] = [{"role": "user", "content": envelope.prompt}]
    metadata.update(envelope.metadata)
    result["metadata"] = metadata
    result.pop("task_bundle_id", None)
    return result


def _policy_map(receipt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("policy")): item
        for item in receipt.get("policies", [])
        if isinstance(item, Mapping)
    }


def receipt_to_reward(receipt: Mapping[str, Any], *, format_valid: bool = True) -> dict[str, Any]:
    """Keep deterministic components separate for GRPO/GDPO normalization."""

    status = receipt.get("status")
    if status == "INVALID":
        return {"valid": False, "retry": True, "reward": 0.0,
                "correctness": None, "format": None, "build": None,
                "api": None, "tests": None}
    policies = _policy_map(receipt)
    g04_facts = policies.get("G04", {}).get("facts", {})
    tests = float(g04_facts.get("score", 0.0)) if isinstance(g04_facts, Mapping) else 0.0
    components = {
        "correctness": float(status == "PASS"),
        "format": float(format_valid),
        "build": float(policies.get("G02", {}).get("status") == "PASS"),
        "api": float(policies.get("G03", {}).get("status") == "PASS"),
        "tests": tests,
    }
    return {"valid": True, "retry": False, "reward": components["correctness"], **components}


def evaluate_response(binding: BundleBinding, response: str, *, finish_reason: str | None = None,
                      executor: str = "docker", invalid_retries: int = 1) -> dict[str, Any]:
    if executor not in {"docker", "host"}:
        raise MediatorError("INVALID_EXECUTOR", executor)
    runner = _set2_runner()
    reconstruction_module = importlib.import_module("candidate_reconstruction")
    attempts: list[dict[str, Any]] = []
    for attempt in range(max(0, invalid_retries) + 1):
        with TemporaryDirectory(prefix="gv2-grpo-mediator-") as temporary:
            output = Path(temporary) / "receipt"
            args = argparse.Namespace(bundle=binding.path, candidate=None, response=response,
                                      finish_reason=finish_reason, output=output,
                                      executor=executor, full=False)
            try:
                value = runner.run(args).payload()
            except reconstruction_module.ReconstructionError as error:
                return {
                    "schema_version": 1, "status": "FAIL", "reason": error.reason,
                    "task_id": binding.task_bundle_id, "policies": [],
                    "returned_files": [], "inherited_files": [], "format_valid": False,
                }
            attempts.append(value)
            if value.get("status") != "INVALID":
                value["mediator_attempts"] = attempt + 1
                return value
    final = dict(attempts[-1])
    final["mediator_attempts"] = len(attempts)
    final["invalid_retry_exhausted"] = True
    return final


def _sample_value(sample: Any, name: str, default: Any = None) -> Any:
    if isinstance(sample, Mapping):
        return sample.get(name, default)
    return getattr(sample, name, default)


def _sample_metadata(sample: Any) -> dict[str, Any]:
    value = _sample_value(sample, "metadata", {})
    return dict(value) if isinstance(value, Mapping) else {}


def _sample_response(sample: Any) -> str:
    for name in ("response", "completion", "output"):
        value = _sample_value(sample, name)
        if isinstance(value, str):
            return value
    return ""


def score_sample(sample: Any, registry: TaskBundleRegistry, *, executor: str,
                 invalid_retries: int) -> dict[str, Any]:
    metadata = _sample_metadata(sample)
    try:
        task_bundle_id = metadata.get("task_bundle_id")
        if not isinstance(task_bundle_id, str):
            raise MediatorError("MISSING_TASK_BUNDLE_ID", "rollout lacks task_bundle_id")
        binding = registry.resolve(task_bundle_id)
        envelope = build_prompt(binding)
        for key, expected in envelope.metadata.items():
            if metadata.get(key) != expected:
                raise MediatorError("PROMPT_BINDING_MISMATCH", key)
        receipt = evaluate_response(binding, _sample_response(sample),
                                    finish_reason=_sample_value(sample, "finish_reason"),
                                    executor=executor, invalid_retries=invalid_retries)
        projection = receipt_to_reward(receipt, format_valid=receipt.get("format_valid", True))
        return {
            "score": projection["reward"], "reward": projection["reward"],
            "infrastructure_error": not projection["valid"],
            "reason": "verifier_invalid" if not projection["valid"] else str(receipt.get("reason", receipt["status"])).lower(),
            "task_bundle_id": task_bundle_id, "bundle_sha256": binding.bundle_sha256,
            "prompt_sha256": envelope.metadata["prompt_sha256"],
            "reward_components": projection, "verifier_receipt": receipt,
            "rollout_id": _sample_value(sample, "rollout_id"),
        }
    except MediatorError as error:
        return {"score": 0.0, "reward": 0.0, "infrastructure_error": True,
                "reason": error.reason, "exception": str(error),
                "rollout_id": _sample_value(sample, "rollout_id")}
    except Exception as error:  # protects remote reward workers
        return {"score": 0.0, "reward": 0.0, "infrastructure_error": True,
                "reason": "MEDIATOR_EXCEPTION",
                "exception": f"{type(error).__name__}: {error}",
                "rollout_id": _sample_value(sample, "rollout_id")}


def _settings() -> tuple[TaskBundleRegistry, str, int]:
    registry = TaskBundleRegistry(Path(os.environ.get(REGISTRY_ENV, DEFAULT_REGISTRY)))
    executor = os.environ.get(EXECUTOR_ENV, "docker")
    retries = int(os.environ.get(RETRIES_ENV, "1"))
    return registry, executor, max(0, retries)


async def reward_func(_args: Any, sample: Any, **_kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Miles custom-RM hook; INVALID records are neutral and marked for exclusion."""

    registry, executor, retries = _settings()
    if isinstance(sample, list):
        return list(await asyncio.gather(*(
            asyncio.to_thread(score_sample, item, registry, executor=executor,
                              invalid_retries=retries) for item in sample
        )))
    return await asyncio.to_thread(score_sample, sample, registry, executor=executor,
                                   invalid_retries=retries)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--task-bundle-id", required=True)
    parser.add_argument("--print-prompt", action="store_true")
    args = parser.parse_args()
    envelope = build_prompt(TaskBundleRegistry(args.registry).resolve(args.task_bundle_id))
    if args.print_prompt:
        print(envelope.prompt, end="")
    else:
        print(json.dumps({"metadata": envelope.metadata}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
