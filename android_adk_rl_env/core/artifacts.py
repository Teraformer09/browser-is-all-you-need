"""Standardized run artifact writer."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from android_adk_rl_env.core.metrics import benchmark_alignment_metadata, summarize_task_results


class ArtifactWriter:
    """Writes rollout and benchmark artifacts under artifacts/runs/{run_id}."""

    artifact_version = "1.0"

    def __init__(self, root: str | Path = "artifacts/runs", run_id: str | None = None) -> None:
        self.root = Path(root)
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.root / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._rollout_path = self.run_dir / "rollout.jsonl"
        self._reward_path = self.run_dir / "reward_trace.jsonl"

    def write_config(self, config: dict[str, Any]) -> None:
        self._write_json("config.json", {"run_id": self.run_id, **config})

    def append_rollout(self, row: dict[str, Any]) -> None:
        self._append_jsonl(self._rollout_path, row)

    def append_reward(self, row: dict[str, Any]) -> None:
        self._append_jsonl(self._reward_path, row)

    def write_summary(
        self,
        backend: str,
        policy: str,
        task_results: list[dict[str, Any]],
        started_at: str,
        ended_at: str,
    ) -> dict[str, Any]:
        task_count = len(task_results)
        success_count = sum(1 for result in task_results if result.get("exact_success") or result.get("success"))
        average_reward = (
            sum(float(result.get("reward", result.get("final_reward", 0.0))) for result in task_results) / task_count
            if task_count
            else 0.0
        )
        metrics = summarize_task_results(task_results)
        summary = {
            "run_id": self.run_id,
            "repo_commit": self._git_sha(),
            "backend": backend,
            "policy": policy,
            "task_count": task_count,
            "success_count": success_count,
            "success_rate": success_count / task_count if task_count else 0.0,
            "average_reward": average_reward,
            "started_at": started_at,
            "ended_at": ended_at,
            "artifact_version": self.artifact_version,
            **metrics,
            "benchmark_alignment": benchmark_alignment_metadata(),
        }
        self._write_json("summary.json", summary)
        return summary

    def write_device_info(self, data: dict[str, Any]) -> None:
        self._write_json("device_info.json", data)

    def write_apk_info(self, data: dict[str, Any]) -> None:
        self._write_json("apk_info.json", data)

    def write_logcat(self, text: str = "") -> None:
        (self.run_dir / "logcat.txt").write_text(text, encoding="utf-8")

    def write_placeholder_media(self) -> None:
        (self.run_dir / "final_screen.png").write_bytes(b"")
        (self.run_dir / "emulator_run.mp4").write_bytes(b"")

    def write_replay(self, task_results: list[dict[str, Any]]) -> None:
        rows = "\n".join(
            "<tr>"
            f"<td>{_html(result.get('task_id', ''))}</td>"
            f"<td>{_html(result.get('episode_id', ''))}</td>"
            f"<td>{_html(result.get('instruction', result.get('goal', '')))}</td>"
            f"<td>{_html(str(result.get('reward', result.get('final_reward', 0.0))))}</td>"
            f"<td>{_html(str(result.get('exact_success', result.get('success', False))))}</td>"
            "</tr>"
            for result in task_results
        )
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mobile Android RL Replay {self.run_id}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>Mobile Android RL Replay</h1>
  <p>Run ID: {self.run_id}</p>
  <table>
    <thead><tr><th>Task</th><th>Episode</th><th>Instruction</th><th>Reward</th><th>Exact Success</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
        (self.run_dir / "replay.html").write_text(html, encoding="utf-8")

    def ensure_required_files(self) -> None:
        for name, default in {
            "config.json": {},
            "summary.json": {},
            "rollout.jsonl": "",
            "reward_trace.jsonl": "",
            "logcat.txt": "",
            "device_info.json": {},
            "apk_info.json": {},
        }.items():
            path = self.run_dir / name
            if path.exists():
                continue
            if isinstance(default, dict):
                path.write_text(json.dumps(default, indent=2, sort_keys=True), encoding="utf-8")
            else:
                path.write_text(default, encoding="utf-8")
        if not (self.run_dir / "replay.html").exists():
            self.write_replay([])
        self.write_placeholder_media()

    def _write_json(self, name: str, data: dict[str, Any]) -> None:
        (self.run_dir / name).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _git_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            return "unknown"
        return result.stdout.strip() or "unknown"


def _html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
