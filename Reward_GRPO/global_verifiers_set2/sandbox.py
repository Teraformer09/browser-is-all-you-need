"""Task-independent command sandbox with deterministic resource receipts."""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class Limits:
    timeout_s: int = 120
    memory_mb: int = 2048
    pids: int = 128
    cpus: float = 2.0
    output_bytes: int = 1_000_000


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    launch_error: str | None
    stdout_truncated: bool
    stderr_truncated: bool


def _trim(data: bytes, limit: int) -> tuple[str, bool]:
    truncated = len(data) > limit
    return data[:limit].decode("utf-8", "replace"), truncated


def run_host(
    command: Sequence[str], cwd: Path, limits: Limits, env: Mapping[str, str] | None = None
) -> CommandResult:
    """Execute an argument array; intended for tests and already-isolated workers."""
    if not command or not all(isinstance(value, str) and value for value in command):
        raise ValueError("command must be a non-empty argument array")
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, capture_output=True, timeout=limits.timeout_s,
            env={"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "LANG": "C", **(env or {})},
        )
        out, out_cut = _trim(completed.stdout, limits.output_bytes)
        err, err_cut = _trim(completed.stderr, limits.output_bytes)
        return CommandResult(tuple(command), completed.returncode, out, err,
                             time.monotonic() - started, False, None, out_cut, err_cut)
    except subprocess.TimeoutExpired as error:
        out, out_cut = _trim(error.stdout or b"", limits.output_bytes)
        err, err_cut = _trim(error.stderr or b"", limits.output_bytes)
        return CommandResult(tuple(command), None, out, err, time.monotonic() - started,
                             True, None, out_cut, err_cut)
    except OSError as error:
        return CommandResult(tuple(command), None, "", "", time.monotonic() - started,
                             False, f"{type(error).__name__}: {error}", False, False)


def run_docker(
    command: Sequence[str], workspace: Path, image: str, limits: Limits,
    *, docker: str = "docker", env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run a command in a locked-down, networkless container."""
    if not image or any(character.isspace() for character in image):
        raise ValueError("a safe pinned container image is required")
    workspace = workspace.resolve(strict=True)
    args = [
        docker, "run", "--rm", "--network=none", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--read-only",
        f"--memory={limits.memory_mb}m", f"--pids-limit={limits.pids}",
        f"--cpus={limits.cpus}", "--tmpfs=/tmp:rw,exec,nosuid,nodev,size=256m",
        "--mount", f"type=bind,src={workspace},dst=/workspace,rw",
        "--workdir=/workspace",
    ]
    for key, value in sorted((env or {}).items()):
        args.extend(["--env", f"{key}={value}"])
    args.extend([image, *command])
    return run_host(args, workspace, limits)


def result_facts(result: CommandResult) -> dict[str, object]:
    return {
        "command": list(result.command), "returncode": result.returncode,
        "duration_s": round(result.duration_s, 6), "timed_out": result.timed_out,
        "launch_error": result.launch_error,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
        "stdout": result.stdout, "stderr": result.stderr,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
    }
