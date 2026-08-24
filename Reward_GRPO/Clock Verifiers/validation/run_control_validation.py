from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


VALIDATION_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = VALIDATION_ROOT.parent
REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    REPO_ROOT
    / "local-results/job22-iter5-fixed26-v5-pathfix-20260814T071410Z"
    / "benchmark-output-shard-0/cpp/exercises/practice/clock"
)
VERIFIER_ROOT = PACKAGE_ROOT / "verifiers"
SOURCE_FILES = ("clock.h", "clock.cpp")
PINNED_INSTRUCTIONS = VALIDATION_ROOT / "fixed/instructions.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verifier(number: int) -> Path:
    matches = sorted(VERIFIER_ROOT.glob(f"verifier_{number:02d}_*.py"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one E{number:02d} verifier, found {matches}")
    return matches[0]


def run_verifier(number: int, exercise: Path, output: Path, compiler: str = "g++") -> dict[str, Any]:
    process = subprocess.run(
        [
            "python3",
            str(verifier(number)),
            "--exercise-dir",
            str(exercise),
            "--output-dir",
            str(output),
            "--compiler",
            compiler,
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    receipt_path = output / "verification_receipt.json"
    if not receipt_path.is_file():
        raise RuntimeError(
            f"E{number:02d} did not write a receipt: rc={process.returncode}; "
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


def reference_sources() -> dict[str, str]:
    return {
        "clock.h": (FIXTURE / ".meta/example.h").read_text(encoding="utf-8"),
        "clock.cpp": (FIXTURE / ".meta/example.cpp").read_text(encoding="utf-8"),
    }


def saved_sources(case_id: str) -> dict[str, str]:
    root = VALIDATION_ROOT / "cases" / case_id
    return {name: (root / name).read_text(encoding="utf-8") for name in SOURCE_FILES}


def plus_one_minute_mutant() -> dict[str, str]:
    sources = reference_sources()
    old = "minute_ += minutes;"
    new = "minute_ += minutes + 1;"
    if sources["clock.cpp"].count(old) != 1:
        raise RuntimeError("reference plus statement drifted")
    sources["clock.cpp"] = sources["clock.cpp"].replace(old, new, 1)
    return sources


def prepare_exercise(root: Path, sources: dict[str, str]) -> Path:
    exercise = root / "exercise"
    shutil.copytree(FIXTURE, exercise, symlinks=False)
    shutil.copy2(PINNED_INSTRUCTIONS, exercise / ".docs/instructions.md")
    for name in SOURCE_FILES:
        (exercise / name).write_text(sources[name], encoding="utf-8")
    return exercise


def candidate_case(case_id: str, sources: dict[str, str], output_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"clock-{case_id}-") as temporary:
        exercise = prepare_exercise(Path(temporary), sources)
        before = {name: sha256(exercise / name) for name in SOURCE_FILES}
        policies = {
            f"E{number:02d}": run_verifier(
                number, exercise, output_root / "candidate_cases" / case_id / f"E{number:02d}"
            )
            for number in range(1, 6)
        }
        after = {name: sha256(exercise / name) for name in SOURCE_FILES}
        return {
            "case_id": case_id,
            "candidate_sha256": before,
            "source_unchanged": before == after,
            "policies": policies,
        }


def invalid_case(case_id: str, kind: str, output_root: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"clock-{case_id}-") as temporary:
        exercise = prepare_exercise(Path(temporary), reference_sources())
        compiler = "g++"
        if kind == "tampered_official_test":
            with (exercise / "clock_test.cpp").open("a", encoding="utf-8") as stream:
                stream.write("\n// validation tamper\n")
        elif kind == "missing_compiler":
            compiler = "clock-validator-compiler-does-not-exist"
        else:
            raise RuntimeError(f"unknown invalid case: {kind}")
        result = run_verifier(3, exercise, output_root / "invalid_cases" / case_id, compiler)
        return {"case_id": case_id, "kind": kind, "policy": "E03", "result": result}


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
    compiler = subprocess.check_output(
        ["g++", "-dumpfullversion", "-dumpversion"], text=True
    ).strip()
    if compiler != "13.3.0":
        raise SystemExit(f"expected GCC 13.3.0, observed {compiler}")

    case_sources = {
        "reference_positive": reference_sources(),
        "midband_trial_2_positive": saved_sources("midband_rl_v2_trial_2_final"),
        "midband_trial_3_positive": saved_sources("midband_rl_v2_trial_3_final"),
        "trial_1_normalization_failure": saved_sources("midband_rl_v2_trial_1_turn_1"),
        "trial_1_duplicate_definitions_failure": saved_sources("midband_rl_v2_trial_1_final"),
        "trial_4_normalization_failure": saved_sources("midband_rl_v2_trial_4_turn_1"),
        "trial_4_static_const_repair_failure": saved_sources("midband_rl_v2_trial_4_final"),
        "plus_one_minute_mutant": plus_one_minute_mutant(),
        "reference_repeat": reference_sources(),
    }
    candidates = [
        candidate_case(case_id, sources, args.output_dir)
        for case_id, sources in case_sources.items()
    ]
    invalid = [
        invalid_case("tampered_official_test", "tampered_official_test", args.output_dir),
        invalid_case("missing_compiler", "missing_compiler", args.output_dir),
    ]
    by_id = {case["case_id"]: case for case in candidates}
    if any(not case["source_unchanged"] for case in candidates):
        raise RuntimeError("a verifier changed candidate source bytes")
    for case_id in (
        "reference_positive",
        "midband_trial_2_positive",
        "midband_trial_3_positive",
        "reference_repeat",
    ):
        statuses = {policy: row["status"] for policy, row in by_id[case_id]["policies"].items()}
        if set(statuses.values()) != {"pass"}:
            raise RuntimeError(f"valid implementation was restricted: {case_id} {statuses}")
    for case_id in (
        "trial_1_normalization_failure",
        "trial_1_duplicate_definitions_failure",
        "trial_4_normalization_failure",
        "trial_4_static_const_repair_failure",
        "plus_one_minute_mutant",
    ):
        policies = by_id[case_id]["policies"]
        if policies["E03"]["status"] != "fail":
            raise RuntimeError(f"terminal gate accepted known defect: {case_id}")
        if all(policies[policy]["status"] == "pass" for policy in ("E01", "E02", "E04", "E05")):
            raise RuntimeError(f"no shaped policy detected known defect: {case_id}")
    if any(case["result"]["status"] != "invalid" for case in invalid):
        raise RuntimeError("an evaluator fault was charged to candidate code")
    first = by_id["reference_positive"]["policies"]
    repeat = by_id["reference_repeat"]["policies"]
    repeatability = {
        policy: {
            "first_status": first[policy]["status"],
            "repeat_status": repeat[policy]["status"],
            "first_kernel_vector": first[policy]["kernel_vector"],
            "repeat_kernel_vector": repeat[policy]["kernel_vector"],
            "decision_equal": (
                first[policy]["status"] == repeat[policy]["status"]
                and first[policy]["kernel_vector"] == repeat[policy]["kernel_vector"]
            ),
        }
        for policy in sorted(first)
    }
    if not all(row["decision_equal"] for row in repeatability.values()):
        raise RuntimeError("reference decisions changed on repeat")

    payload = {
        "schema_version": 1,
        "task_id": "local-aider-cpp/clock",
        "compiler": compiler,
        "pinned_instructions_sha256": sha256(PINNED_INSTRUCTIONS),
        "candidate_cases": candidates,
        "invalid_cases": invalid,
        "repeatability": repeatability,
    }
    receipt = args.output_dir / "control_validation_receipt.json"
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": str(receipt),
        "receipt_sha256": sha256(receipt),
        "positive_cases": 3,
        "defect_cases": 5,
        "invalid_cases": 2,
        "repeatable_policies": sum(row["decision_equal"] for row in repeatability.values()),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
