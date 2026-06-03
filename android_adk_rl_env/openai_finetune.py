"""Prepare and submit OpenAI supervised fine-tuning jobs from APK rollouts."""

from __future__ import annotations

import argparse
import json
import os
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from android_adk_rl_env.config import get_openai_api_key
from android_adk_rl_env.policies.openai_policy import SYSTEM_INSTRUCTIONS
from android_adk_rl_env.tasks.dummy_apk import DummyApkFormSearchTask

OPENAI_BASE_URL = "https://api.openai.com/v1"


def compact_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal": observation.get("goal"),
        "steps": observation.get("steps"),
        "max_steps": observation.get("max_steps"),
        "ui": observation.get("ui", []),
        "last_action": observation.get("last_action"),
        "last_error": observation.get("last_error"),
        "expected_state": observation.get("expected_state"),
        "reward_components": observation.get("reward_components"),
        "final_reward": observation.get("final_reward"),
    }


def messages_for_action(observation: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {
                "role": "user",
                "content": "Observation JSON:\n" + json.dumps(compact_observation(observation), sort_keys=True),
            },
            {"role": "assistant", "content": json.dumps(action, sort_keys=True)},
        ]
    }


def load_rollouts(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def examples_from_rollouts(rollouts: list[dict[str, Any]], include_failures: bool = False) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for rollout in rollouts:
        if not include_failures and not rollout.get("success"):
            continue
        for transition in rollout.get("transitions", []):
            action = transition.get("action", {})
            if action.get("action") == "finish":
                continue
            examples.append(messages_for_action(transition.get("observation", {}), action))
    return examples


def scripted_bootstrap_examples() -> list[dict[str, Any]]:
    task = DummyApkFormSearchTask()
    empty_ui = [
        {"id": name, "text": "", "focused": False, "bounds": [], "center": []}
        for name in task.resource_names
    ]
    base = {
        "task": task.name_label,
        "goal": task.goal,
        "steps": 0,
        "max_steps": task.max_steps,
        "ui": empty_ui,
        "last_action": None,
        "last_error": None,
        "expected_state": task.expected_state(),
        "reward_components": {},
        "final_reward": 0.0,
    }
    actions = [
        {"action": "input_resource", "target": "search_input", "text": task.query},
        {"action": "click_resource", "target": "search_button", "text": None},
        {"action": "input_resource", "target": "name_input", "text": task.name},
        {"action": "input_resource", "target": "email_input", "text": task.email},
        {"action": "press_back", "target": None, "text": None},
        {"action": "click_resource", "target": "submit_button", "text": None},
    ]
    examples: list[dict[str, Any]] = []
    observation = dict(base)
    for step, action in enumerate(actions):
        observation = dict(observation)
        observation["steps"] = step
        examples.append(messages_for_action(observation, action))
        observation["last_action"] = action
    return examples


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


class OpenAIFineTuneClient:
    def __init__(self, api_key: str | None = None, base_url: str = OPENAI_BASE_URL) -> None:
        self.api_key = api_key or get_openai_api_key()
        self.base_url = base_url.rstrip("/")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required to upload files or create fine-tuning jobs")

    def upload_training_file(self, path: str | Path) -> dict[str, Any]:
        return self._multipart_post(
            "/files",
            fields={"purpose": "fine-tune"},
            file_field="file",
            file_path=Path(path),
        )

    def create_fine_tuning_job(
        self,
        training_file_id: str,
        model: str,
        suffix: str | None = None,
        validation_file_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"training_file": training_file_id, "model": model}
        if suffix:
            payload["suffix"] = suffix
        if validation_file_id:
            payload["validation_file"] = validation_file_id
        return self._json_post("/fine_tuning/jobs", payload)

    def _json_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        return self._open(request)

    def _multipart_post(
        self,
        path: str,
        fields: dict[str, str],
        file_field: str,
        file_path: Path,
    ) -> dict[str, Any]:
        boundary = "----android-adk-rl-" + uuid.uuid4().hex
        body = bytearray()
        crlf = b"\r\n"
        for name, value in fields.items():
            body.extend(f"--{boundary}".encode() + crlf)
            body.extend(f"Content-Disposition: form-data; name=\"{name}\"".encode() + crlf + crlf)
            body.extend(value.encode())
            body.extend(crlf)
        body.extend(f"--{boundary}".encode() + crlf)
        body.extend(
            f"Content-Disposition: form-data; name=\"{file_field}\"; filename=\"{file_path.name}\"".encode()
            + crlf
        )
        body.extend(b"Content-Type: application/jsonl" + crlf + crlf)
        body.extend(file_path.read_bytes())
        body.extend(crlf)
        body.extend(f"--{boundary}--".encode() + crlf)

        request = urllib.request.Request(
            self.base_url + path,
            data=bytes(body),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        return self._open(request)

    def _open(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=120.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Create SFT JSONL from rollout JSONL.")
    prepare.add_argument("--rollouts", required=True)
    prepare.add_argument("--output", default="artifacts/openai/dummy_apk_sft.jsonl")
    prepare.add_argument("--include-failures", action="store_true")

    bootstrap = subparsers.add_parser("prepare-scripted", help="Create a tiny bootstrap SFT JSONL without ADB.")
    bootstrap.add_argument("--output", default="artifacts/openai/dummy_apk_sft_bootstrap.jsonl")

    submit = subparsers.add_parser("submit", help="Upload JSONL and create a supervised fine-tuning job.")
    submit.add_argument("--training-file", required=True)
    submit.add_argument("--model", default="gpt-4o-mini")
    submit.add_argument("--suffix", default="dummy-apk-rl")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "prepare":
        rows = examples_from_rollouts(load_rollouts(args.rollouts), include_failures=args.include_failures)
        write_jsonl(args.output, rows)
        print(json.dumps({"examples": len(rows), "output": args.output}, sort_keys=True))
        return

    if args.command == "prepare-scripted":
        rows = scripted_bootstrap_examples()
        write_jsonl(args.output, rows)
        print(json.dumps({"examples": len(rows), "output": args.output}, sort_keys=True))
        return

    if args.command == "submit":
        client = OpenAIFineTuneClient()
        uploaded = client.upload_training_file(args.training_file)
        job = client.create_fine_tuning_job(
            training_file_id=uploaded["id"],
            model=args.model,
            suffix=args.suffix,
        )
        print(json.dumps({"file": uploaded, "job": job}, indent=2, sort_keys=True))
        return


if __name__ == "__main__":
    main()
