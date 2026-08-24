from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import tokenize
from pathlib import Path
from typing import Any


VALIDATION_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = VALIDATION_ROOT.parent
POLICY_ROOT = PACKAGE_ROOT / "Verifier implementation policy"
VERIFIER_ROOT = PACKAGE_ROOT / "verifiers"
EXPECTED_KERNELS = {
    "E01": 5,
    "E02": 4,
    "E03": 4,
    "E04": 3,
    "E05": 3,
    "E06": 5,
    "E07": 5,
    "E08": 6,
    "E09": 4,
    "E10": 4,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comments(source: str) -> list[str]:
    return [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]


def documented_kernels(path: Path, policy_id: str) -> list[str]:
    prefix = str(int(policy_id[1:]))
    values = re.findall(r"\|\s*(\d+[A-Z])\s*\|", path.read_text(encoding="utf-8"))
    return sorted({value for value in values if value.startswith(prefix)})


def inspect_verifier(path: Path, policy_id: str) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    prefix = str(int(policy_id[1:]))
    functions = sorted(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and re.fullmatch(rf"verify_{prefix}[a-z]_.+", node.name)
    )
    kernel_ids = sorted(
        f"{prefix}{chr(ord('A') + index)}" for index in range(len(functions))
    )
    source_comments = comments(source)
    has_cli = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        for node in tree.body
    )
    return {
        "path": str(path.relative_to(PACKAGE_ROOT)),
        "sha256": sha256(path),
        "ast_parse": "PASS",
        "verify_functions": functions,
        "kernel_ids": kernel_ids,
        "kernel_count": len(functions),
        "expected_kernel_count": EXPECTED_KERNELS[policy_id],
        "kernel_count_match": len(functions) == EXPECTED_KERNELS[policy_id],
        "python_comment_count": len(source_comments),
        "one_source_comment": len(source_comments) == 1,
        "cli_entrypoint_present": has_cli,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any(args.output_dir.iterdir()):
        raise SystemExit("--output-dir must be empty")
    policies = sorted(POLICY_ROOT.glob("policy_[0-9][0-9]_*.md"))
    verifiers = sorted(VERIFIER_ROOT.glob("verifier_[0-9][0-9]_*.py"))
    if len(policies) != 10 or len(verifiers) != 10:
        raise SystemExit(
            f"expected ten policies and ten verifiers, observed {len(policies)} and {len(verifiers)}"
        )
    policy_by_id = {f"E{path.name[7:9]}": path for path in policies}
    verifier_by_id = {f"E{path.name[9:11]}": path for path in verifiers}
    if set(policy_by_id) != set(EXPECTED_KERNELS) or set(verifier_by_id) != set(EXPECTED_KERNELS):
        raise SystemExit("policy/verifier numeric pairing does not cover E01-E10 exactly")
    verifier_results = {
        policy_id: inspect_verifier(verifier_by_id[policy_id], policy_id)
        for policy_id in sorted(EXPECTED_KERNELS)
    }
    policy_results = {
        policy_id: {
            "path": str(path.relative_to(PACKAGE_ROOT)),
            "sha256": sha256(path),
            "nonempty": path.stat().st_size > 0,
            "documented_kernel_ids": documented_kernels(path, policy_id),
            "paired_verifier": verifier_results[policy_id]["path"],
        }
        for policy_id, path in sorted(policy_by_id.items())
    }
    failures: list[str] = []
    for policy_id in sorted(EXPECTED_KERNELS):
        verifier_row = verifier_results[policy_id]
        policy_row = policy_results[policy_id]
        if not verifier_row["kernel_count_match"]:
            failures.append(f"{policy_id}:implementation-kernel-count")
        if not verifier_row["one_source_comment"]:
            failures.append(f"{policy_id}:comment-count")
        if not verifier_row["cli_entrypoint_present"]:
            failures.append(f"{policy_id}:cli-entrypoint")
        if policy_row["documented_kernel_ids"] != verifier_row["kernel_ids"]:
            failures.append(f"{policy_id}:documented-kernel-ids")
        if not policy_row["nonempty"]:
            failures.append(f"{policy_id}:empty-policy")
    helper = VERIFIER_ROOT / "_grade_school_common.py"
    ast.parse(helper.read_text(encoding="utf-8"), filename=str(helper))
    if failures:
        raise SystemExit(f"structure assertions failed: {failures}")
    payload = {
        "schema_version": 1,
        "task_id": "local-aider-cpp/grade-school",
        "status": "PASS",
        "policy_count": len(policy_results),
        "verifier_count": len(verifier_results),
        "shared_helper": {
            "path": str(helper.relative_to(PACKAGE_ROOT)),
            "sha256": sha256(helper),
            "ast_parse": "PASS",
        },
        "applicable_kernel_count_by_policy": EXPECTED_KERNELS,
        "candidate_source_kernel_count": sum(
            EXPECTED_KERNELS[key]
            for key in ("E01", "E02", "E03", "E04", "E05", "E06", "E09", "E10")
        ),
        "static_replay_kernel_count": sum(
            EXPECTED_KERNELS[key]
            for key in ("E01", "E02", "E03", "E04", "E05", "E06", "E09")
        ),
        "complete_campaign_kernel_count": sum(EXPECTED_KERNELS.values()),
        "policies": policy_results,
        "verifiers": verifier_results,
    }
    receipt = args.output_dir / "structure_validation_receipt.json"
    receipt.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "receipt": str(receipt),
                "receipt_sha256": sha256(receipt),
                "status": payload["status"],
                "policies": payload["policy_count"],
                "verifiers": payload["verifier_count"],
                "source_kernels": payload["candidate_source_kernel_count"],
                "complete_kernels": payload["complete_campaign_kernel_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
