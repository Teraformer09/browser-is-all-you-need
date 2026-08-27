"""G04: run authenticated official tests against G02 candidate objects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from receipt import PolicyReceipt, policy
from sandbox import CommandResult, Limits, result_facts

Execute = Callable[[list[str], Path, Limits, dict[str, str] | None], CommandResult]
COUNT = re.compile(r"(?:tests[_ ]?)?passed\s*[:=]\s*(\d+)\s*/\s*(\d+)", re.I)


def verify(workspace: Path, manifest: dict[str, Any], objects: list[str], execute: Execute,
           limits: Limits) -> PolicyReceipt:
    functional = manifest.get("functional", {})
    build = manifest.get("build", {})
    test_source = functional.get("test_source")
    if not isinstance(test_source, str):
        return policy("G04", "INVALID", "FUNCTIONAL_ORACLE_MISSING")
    binary = ".gv2/official_tests"
    compile_command = [str(build.get("compiler", "g++")),
                       f"-std={build.get('standard', 'c++17')}",
                       *(str(value) for value in build.get("flags", [])), "-I.",
                       test_source, *objects,
                       *(f"-l{value}" for value in build.get("libraries", [])), "-o", binary]
    compiled = execute(compile_command, workspace, limits, None)
    if compiled.launch_error or compiled.timed_out:
        return policy("G04", "INVALID", "TEST_BUILD_INFRASTRUCTURE_FAILURE",
                      compile=result_facts(compiled))
    if compiled.returncode != 0:
        return policy("G04", "FAIL", "TEST_COMPILE_FAIL",
                      compile=result_facts(compiled))
    executed = execute([f"./{binary}"], workspace, limits, None)
    if executed.launch_error:
        return policy("G04", "INVALID", "TEST_RUNNER_UNAVAILABLE", run=result_facts(executed))
    if executed.timed_out:
        return policy("G04", "FAIL", "CANDIDATE_RUNTIME_TIMEOUT", run=result_facts(executed))
    match = COUNT.search(executed.stdout)
    passed = int(match.group(1)) if match else int(executed.returncode == 0)
    total = int(match.group(2)) if match else 1
    if total < 1 or passed < 0 or passed > total:
        return policy("G04", "INVALID", "MALFORMED_TEST_COUNT", run=result_facts(executed))
    status = "PASS" if executed.returncode == 0 and passed == total else "FAIL"
    return policy("G04", status, "FUNCTIONAL_PASS" if status == "PASS" else "SEMANTIC_FAIL",
                  tests_passed=passed, tests_total=total, score=passed / total,
                  compile=result_facts(compiled), run=result_facts(executed))
