"""Portable orchestrator for the manifest-driven Global Verifiers Set 2."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path, PurePath
from tempfile import TemporaryDirectory
from typing import Any

import candidate_reconstruction
import g01_integrity
import g02_build
import g03_api_link
import g04_functional
import g05_safety
import g07_portability
from receipt import PolicyReceipt, VerificationReceipt, policy
from sandbox import Limits, result_facts, run_docker, run_host

MANDATORY = ("G01", "G02", "G03", "G04")
OPTIONAL = ("G05", "G07")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty relative path")
    path = PurePath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} is unsafe")
    return value


def load_bundle(bundle: Path) -> tuple[dict[str, Any], str]:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("task bundle lacks a regular manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("schema_version") != 2
        or not isinstance(manifest.get("task_id"), str)
        or not manifest["task_id"]
        or not isinstance(manifest.get("contract_version"), str)
        or not manifest["contract_version"]
    ):
        raise ValueError("unsupported task-bundle manifest")
    editable = manifest.get("editable_files")
    protected = manifest.get("protected_files")
    if not isinstance(editable, list) or not editable or not isinstance(protected, dict):
        raise ValueError("manifest lacks editable/protected file contracts")
    for index, name in enumerate(editable):
        _relative(name, f"editable_files[{index}]")
    if len(set(editable)) != len(editable):
        raise ValueError("editable-file contract contains duplicates")
    for name, digest in protected.items():
        _relative(name, "protected_files")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("protected digest is malformed")
    if set(editable) & set(protected):
        raise ValueError("editable and protected paths overlap")
    contract = manifest.get("api", {}).get("contract")
    for required in ("instructions.md", contract):
        if not isinstance(required, str):
            raise ValueError("task bundle lacks an API contract")
        _relative(required, "required asset")
        path = bundle / required
        if not path.is_file() or path.is_symlink() or required not in protected:
            raise ValueError(f"task bundle lacks protected {required}")
    starter = bundle / "starter"
    if not starter.is_dir() or starter.is_symlink():
        raise ValueError("task bundle lacks a regular starter tree")
    for name in editable:
        path = starter / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"starter lacks editable file {name}")
    preflight = manifest.get("preflight_commands", [])
    if not isinstance(preflight, list) or any(
        not isinstance(command, list)
        or not command
        or not all(isinstance(argument, str) and argument for argument in command)
        for command in preflight
    ):
        raise ValueError("preflight commands must be non-empty argument arrays")
    return manifest, sha256(manifest_path)


def _not_run(identifier: str, prerequisite: str) -> PolicyReceipt:
    return policy(identifier, "NOT_RUN", "PREREQUISITE_FAILED", prerequisite=prerequisite)


def run(args: argparse.Namespace) -> VerificationReceipt:
    bundle = args.bundle.resolve(strict=True)
    manifest, manifest_sha = load_bundle(bundle)
    limits_data = manifest.get("limits", {})
    limits = Limits(timeout_s=int(limits_data.get("timeout_s", 120)),
                    memory_mb=int(limits_data.get("memory_mb", 2048)),
                    pids=int(limits_data.get("pids", 128)),
                    cpus=float(limits_data.get("cpus", 2.0)),
                    output_bytes=int(limits_data.get("output_bytes", 1_000_000)))
    with TemporaryDirectory(prefix="global-verifiers-set2-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(bundle, workspace)
        candidate_input = args.candidate.resolve(strict=True) if args.candidate else None
        reconstruction = candidate_reconstruction.reconstruct(
            workspace / "starter", workspace / "candidate", manifest["editable_files"],
            response=args.response, supplied_dir=candidate_input, finish_reason=args.finish_reason)
        # Fixed assets are copied beside candidate source, never sourced from model output.
        for item in workspace.iterdir():
            if item.name in {"candidate", "starter"}:
                continue
            target = reconstruction.root / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            elif item.is_file():
                shutil.copy2(item, target)
        (reconstruction.root / ".gv2").mkdir()

        if args.executor == "docker":
            image = str(manifest.get("runtime", {}).get("image", ""))
            def execute(command, cwd, command_limits, env):
                return run_docker(command, cwd, image, command_limits, env=env)
        else:
            execute = run_host

        receipts: list[PolicyReceipt] = []
        g01 = g01_integrity.verify(reconstruction.root, manifest)
        receipts.append(g01)
        objects: list[str] = []
        api_binary: str | None = None
        if g01.status == "PASS":
            preflight_results = []
            for command in manifest.get("preflight_commands", []):
                result = execute(command, reconstruction.root, limits, None)
                preflight_results.append(result_facts(result))
                if result.launch_error or result.timed_out or result.returncode != 0:
                    receipts.append(policy("PREFLIGHT", "INVALID", "DEPENDENCY_PREFLIGHT_FAILED",
                                           commands=preflight_results))
                    break
            else:
                g02, objects = g02_build.verify(reconstruction.root,
                                                reconstruction.root / ".gv2/objects",
                                                manifest, execute, limits)
                receipts.append(g02)
                if g02.status == "PASS":
                    g03, api_binary = g03_api_link.verify(reconstruction.root, manifest,
                                                          objects, execute, limits)
                    receipts.append(g03)
                    if g03.status == "PASS":
                        receipts.append(g04_functional.verify(reconstruction.root, manifest,
                                                               objects, execute, limits))
                    else:
                        receipts.append(_not_run("G04", "G03"))
                else:
                    receipts.extend([_not_run("G03", "G02"), _not_run("G04", "G02")])
        else:
            receipts.extend([_not_run(name, "G01") for name in ("G02", "G03", "G04")])

        mandatory = {item.policy: item for item in receipts}
        mandatory_pass = all(mandatory.get(name) and mandatory[name].status == "PASS" for name in MANDATORY)
        if args.full and mandatory_pass:
            receipts.append(g05_safety.verify(reconstruction.root, manifest, execute, limits))
            receipts.append(g07_portability.verify(reconstruction.root, manifest, execute, limits))
        elif args.full:
            receipts.extend([_not_run(name, "G04") for name in OPTIONAL])

        statuses = [item.status for item in receipts if item.policy in MANDATORY or item.policy == "PREFLIGHT"]
        status = "INVALID" if "INVALID" in statuses else "PASS" if mandatory_pass else "FAIL"
        final = VerificationReceipt(2, manifest["task_id"], manifest_sha,
                                    reconstruction.candidate_sha256, status, receipts,
                                    reconstruction.returned_files, reconstruction.inherited_files)
        args.output.mkdir(parents=True, exist_ok=True)
        final.write(args.output / "verification_receipt.json")
        return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--response")
    parser.add_argument("--finish-reason")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executor", choices=("docker", "host"), default="docker")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    if bool(args.candidate) == bool(args.response is not None):
        parser.error("choose exactly one of --candidate or --response")
    try:
        receipt = run(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"INVALID: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(receipt.payload(), sort_keys=True))
    return 0 if receipt.status == "PASS" else 2 if receipt.status == "INVALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
