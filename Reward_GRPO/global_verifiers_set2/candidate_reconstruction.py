"""Safely overlay an Aider whole-file response on an immutable starter tree."""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterable

FENCE = re.compile(r"(?ms)^([^\n`]+?)\s*\n```(?:cpp|c\+\+|cc|hpp|h)?\s*\n(.*?)^```\s*$")


@dataclass(frozen=True)
class Reconstruction:
    root: Path
    returned_files: list[str]
    inherited_files: list[str]
    candidate_sha256: str


class ReconstructionError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _safe(relative: str) -> bool:
    path = PurePath(relative)
    return (
        bool(relative)
        and not path.is_absolute()
        and ".." not in path.parts
        and "." not in path.parts
        and str(path) == relative
    )


def _regular_files(root: Path) -> set[str]:
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ReconstructionError("UNSAFE_CANDIDATE", str(path.relative_to(root)))
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    return files


def tree_sha256(root: Path, files: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        data = (root / name).read_bytes()
        digest.update(name.encode() + b"\0" + data + b"\0")
    return digest.hexdigest()


def reconstruct(
    starter: Path, output: Path, editable_files: list[str], *, response: str | None = None,
    supplied_dir: Path | None = None, finish_reason: str | None = None,
) -> Reconstruction:
    if response is not None and supplied_dir is not None:
        raise ReconstructionError("INVALID_INPUT", "choose response or supplied_dir")
    allowed = set(editable_files)
    if not allowed or any(not _safe(name) for name in allowed):
        raise ReconstructionError("INVALID_MANIFEST", "unsafe editable-file contract")
    shutil.copytree(starter, output, symlinks=False)
    returned: dict[str, bytes] = {}
    if response is not None:
        for match in FENCE.finditer(response):
            label = match.group(1).strip().strip("`:")
            name = PurePath(label).as_posix()
            if name not in allowed or not _safe(name):
                raise ReconstructionError("UNAUTHORIZED_FILE", label)
            if name in returned:
                raise ReconstructionError("DUPLICATE_FILE", name)
            returned[name] = (match.group(2).rstrip() + "\n").encode()
        if not returned:
            reason = "TRUNCATED" if finish_reason == "length" else "INVALID_FORMAT"
            raise ReconstructionError(reason, "no complete editable file was returned")
        if response.count("```") % 2:
            reason = "TRUNCATED" if finish_reason == "length" else "INCOMPLETE_FENCE"
            raise ReconstructionError(reason, "response contains an incomplete code fence")
    elif supplied_dir is not None:
        supplied = _regular_files(supplied_dir)
        unauthorized = sorted(supplied - allowed)
        if unauthorized:
            raise ReconstructionError("UNAUTHORIZED_FILE", unauthorized[0])
        for name in allowed:
            source = supplied_dir / name
            if source.is_file() and not source.is_symlink():
                returned[name] = source.read_bytes()
    else:
        raise ReconstructionError("INVALID_INPUT", "candidate input is absent")
    for name, data in returned.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    inherited = sorted(allowed - set(returned))
    return Reconstruction(output, sorted(returned), inherited, tree_sha256(output, allowed))
