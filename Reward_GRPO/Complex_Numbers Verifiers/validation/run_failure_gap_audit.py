from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


VALIDATION_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = VALIDATION_ROOT.parent
REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    REPO_ROOT
    / "local-results/job22-iter5-fixed26-v5-pathfix-20260814T071410Z"
    / "benchmark-output-shard-0/cpp/exercises/practice/complex-numbers"
)
VERIFIER_ROOT = PACKAGE_ROOT / "verifiers"
SOURCE_FILES = ("complex_numbers.h", "complex_numbers.cpp")
PINNED_INSTRUCTIONS = VALIDATION_ROOT / "fixed/instructions.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verifier(number: int) -> Path:
    matches = sorted(VERIFIER_ROOT.glob(f"verifier_{number:02d}_*.py"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one E{number:02d} verifier, found {matches}")
    return matches[0]


def run_verifier(number: int, exercise: Path, output: Path) -> dict[str, Any]:
    process = subprocess.run(
        ["python3", str(verifier(number)), "--exercise-dir", str(exercise), "--output-dir", str(output)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    receipt_path = output / "verification_receipt.json"
    if not receipt_path.is_file():
        raise RuntimeError(
            f"E{number:02d} did not write receipt: rc={process.returncode}; "
            f"stdout={process.stdout[-1000:]}; stderr={process.stderr[-1000:]}"
        )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {
        "status": receipt["status"],
        "kernel_vector": [item.get("kernel") for item in receipt["kernel_results"]],
        "kernel_statuses": [item.get("status") for item in receipt["kernel_results"]],
        "kernel_summaries": [item.get("summary") for item in receipt["kernel_results"]],
        "candidate_source_sha256": receipt.get("candidate_source_sha256"),
        "preflight_error": receipt.get("preflight_error"),
        "process_returncode": process.returncode,
        "receipt_sha256": sha256(receipt_path),
    }


def classify(source_outcome: str, gate_status: str) -> str:
    source_pass = source_outcome == "pass"
    gate_pass = gate_status == "pass"
    return {
        (True, True): "agreement_pass",
        (True, False): "restriction",
        (False, True): "missed_failure",
        (False, False): "agreement_fail",
    }[(source_pass, gate_pass)]


def replay_case(row: dict[str, Any], output_root: Path) -> dict[str, Any]:
    stored = VALIDATION_ROOT / row["source_path"]
    for name in SOURCE_FILES:
        if sha256(stored / name) != row["candidate_sha256"][name]:
            raise RuntimeError(f"candidate digest mismatch: {row['case_id']}/{name}")
    with tempfile.TemporaryDirectory(prefix="complex-numbers-gap-") as temporary:
        exercise = Path(temporary) / "exercise"
        shutil.copytree(FIXTURE, exercise, symlinks=False)
        shutil.copy2(PINNED_INSTRUCTIONS, exercise / ".docs/instructions.md")
        for name in SOURCE_FILES:
            shutil.copy2(stored / name, exercise / name)
        before = {name: sha256(exercise / name) for name in SOURCE_FILES}
        policies = {
            f"E{number:02d}": run_verifier(
                number, exercise, output_root / "cases" / row["case_id"] / f"E{number:02d}"
            )
            for number in range(1, 6)
        }
        after = {name: sha256(exercise / name) for name in SOURCE_FILES}
        classification = classify(row["source_outcome"], policies["E03"]["status"])
        if classification != row["expected_classification"]:
            raise RuntimeError(
                f"classification drift for {row['case_id']}: "
                f"expected {row['expected_classification']}, observed {classification}"
            )
        return {
            "case_id": row["case_id"],
            "source_sample_id": row["source_sample_id"],
            "source_outcome": row["source_outcome"],
            "failure_class": row["failure_class"],
            "candidate_sha256": before,
            "source_unchanged": before == after,
            "policies": policies,
            "classification": classification,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if os.environ.get("STRANGE_ISOLATED_REPLAY") != "1":
        raise SystemExit("STRANGE_ISOLATED_REPLAY=1 is required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any(args.output_dir.iterdir()):
        raise SystemExit("--output-dir must be empty")
    compiler = subprocess.check_output(["g++", "-dumpfullversion", "-dumpversion"], text=True).strip()
    if compiler != "13.3.0":
        raise SystemExit(f"expected GCC 13.3.0, observed {compiler}")
    manifest_path = VALIDATION_ROOT / "failure_gap_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256(VERIFIER_ROOT / "_contract.py") != manifest["current"]["contract_sha256"]:
        raise SystemExit("contract digest mismatch")
    for policy_id, expected in manifest["current"]["verifier_sha256"].items():
        if sha256(verifier(int(policy_id[1:]))) != expected:
            raise SystemExit(f"verifier digest mismatch: {policy_id}")
    if sha256(FIXTURE / "complex_numbers_test.cpp") != manifest["official"]["test_sha256"]:
        raise SystemExit("official test digest mismatch")
    samples = [replay_case(row, args.output_dir) for row in manifest["cases"]]
    if any(not row["source_unchanged"] for row in samples):
        raise RuntimeError("a verifier changed candidate source bytes")
    counts = Counter(row["classification"] for row in samples)
    if counts.get("missed_failure", 0) or counts.get("restriction", 0):
        raise RuntimeError(f"current verifier disagrees with official outcomes: {counts}")
    payload = {
        "schema_version": 1,
        "task_id": manifest["task_id"],
        "source_run_id": manifest["source_run_id"],
        "source_checkpoint": manifest["source_checkpoint"],
        "compiler": compiler,
        "manifest_sha256": sha256(manifest_path),
        "pinned_instructions_sha256": sha256(PINNED_INSTRUCTIONS),
        "sample_count": len(samples),
        "classification_counts": dict(sorted(counts.items())),
        "samples": samples,
    }
    receipt = args.output_dir / "failure_gap_replay_receipt.json"
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": str(receipt),
        "receipt_sha256": sha256(receipt),
        "classifications": payload["classification_counts"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
