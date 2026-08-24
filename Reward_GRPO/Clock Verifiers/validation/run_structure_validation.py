from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import tokenize
from pathlib import Path
from typing import Any


VALIDATION_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = VALIDATION_ROOT.parent
POLICY_ROOT = PACKAGE_ROOT / "Verifier implementation policy"
VERIFIER_ROOT = PACKAGE_ROOT / "verifiers"
EXPECTED_KERNELS = {f"E{number:02d}": 3 for number in range(1, 6)}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comments(source: str) -> list[str]:
    return [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]


def inspect_verifier(path: Path, policy_id: str) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    values = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id == "POLICY_ID"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    expected_declared = f"CL-{policy_id}"
    check_functions = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "checks"
    ]
    source_comments = comments(source)
    return {
        "path": str(path.relative_to(PACKAGE_ROOT)),
        "sha256": sha256(path),
        "ast_parse": "PASS",
        "declared_policy_id": values[0] if len(values) == 1 else None,
        "policy_id_match": values == [expected_declared],
        "checks_function_count": len(check_functions),
        "checks_function_present": check_functions == ["checks"],
        "expected_kernel_count": EXPECTED_KERNELS[policy_id],
        "python_comment_count": len(source_comments),
        "one_source_comment": len(source_comments) == 1,
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
    if len(policies) != 5 or len(verifiers) != 5:
        raise SystemExit(
            f"expected five policies and five verifiers, observed {len(policies)} and {len(verifiers)}"
        )
    policy_by_id = {f"E{path.name[7:9]}": path for path in policies}
    verifier_by_id = {f"E{path.name[9:11]}": path for path in verifiers}
    if set(policy_by_id) != set(EXPECTED_KERNELS) or set(verifier_by_id) != set(EXPECTED_KERNELS):
        raise SystemExit("policy/verifier numeric pairing does not cover E01-E05 exactly")
    verifier_results = {
        policy_id: inspect_verifier(verifier_by_id[policy_id], policy_id)
        for policy_id in sorted(EXPECTED_KERNELS)
    }
    failures = [
        f"{policy_id}:{field}"
        for policy_id, row in verifier_results.items()
        for field in ("policy_id_match", "checks_function_present", "one_source_comment")
        if not row[field]
    ]
    if failures:
        raise SystemExit(f"structure assertions failed: {failures}")
    policy_results = {
        policy_id: {
            "path": str(path.relative_to(PACKAGE_ROOT)),
            "sha256": sha256(path),
            "nonempty": path.stat().st_size > 0,
            "paired_verifier": verifier_results[policy_id]["path"],
        }
        for policy_id, path in sorted(policy_by_id.items())
    }
    if any(not row["nonempty"] for row in policy_results.values()):
        raise SystemExit("a Clock policy file is empty")
    payload = {
        "schema_version": 1,
        "task_id": "local-aider-cpp/clock",
        "status": "PASS",
        "policy_count": len(policy_results),
        "verifier_count": len(verifier_results),
        "applicable_kernel_count_by_policy": EXPECTED_KERNELS,
        "candidate_kernel_count": sum(EXPECTED_KERNELS.values()),
        "policies": policy_results,
        "verifiers": verifier_results,
    }
    receipt = args.output_dir / "structure_validation_receipt.json"
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": str(receipt),
        "receipt_sha256": sha256(receipt),
        "status": payload["status"],
        "policies": payload["policy_count"],
        "verifiers": payload["verifier_count"],
        "kernels": payload["candidate_kernel_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
