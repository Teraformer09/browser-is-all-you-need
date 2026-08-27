"""G05: optional manifest-driven ASan/UBSan diagnostic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from receipt import PolicyReceipt, policy
from sandbox import CommandResult, Limits, result_facts

Execute = Callable[[list[str], Path, Limits, dict[str, str] | None], CommandResult]


def verify(workspace: Path, manifest: dict[str, Any], execute: Execute,
           limits: Limits) -> PolicyReceipt:
    build, functional = manifest.get("build", {}), manifest.get("functional", {})
    sources, test_source = build.get("sources", []), functional.get("test_source")
    if not sources or not isinstance(test_source, str):
        return policy("G05", "INVALID", "SAFETY_WORKLOAD_MISSING")
    binary = ".gv2/safety_tests"
    command = [str(build.get("compiler", "g++")), f"-std={build.get('standard', 'c++17')}",
               "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
               "-I.", *(str(value) for value in sources), test_source,
               *(f"-l{value}" for value in build.get("libraries", [])), "-o", binary]
    compiled = execute(command, workspace, limits, None)
    if compiled.launch_error or compiled.timed_out:
        return policy("G05", "INVALID", "SANITIZER_TOOLCHAIN_UNAVAILABLE",
                      compile=result_facts(compiled))
    if compiled.returncode != 0:
        return policy("G05", "FAIL", "SANITIZER_BUILD_FAIL", compile=result_facts(compiled))
    run = execute([f"./{binary}"], workspace, limits,
                  {"ASAN_OPTIONS": "halt_on_error=1:detect_leaks=1",
                   "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"})
    if run.launch_error:
        return policy("G05", "INVALID", "SANITIZER_RUNTIME_UNAVAILABLE", run=result_facts(run))
    if run.timed_out:
        return policy("G05", "FAIL", "SANITIZER_TIMEOUT", run=result_facts(run))
    return policy("G05", "PASS" if run.returncode == 0 else "FAIL",
                  "SAFETY_PASS" if run.returncode == 0 else "SANITIZER_FAIL",
                  compile=result_facts(compiled), run=result_facts(run))
