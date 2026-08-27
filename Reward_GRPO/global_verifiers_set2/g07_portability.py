"""G07: optional alternate-toolchain build and functional diagnostic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from receipt import PolicyReceipt, policy
from sandbox import CommandResult, Limits, result_facts

Execute = Callable[[list[str], Path, Limits, dict[str, str] | None], CommandResult]


def verify(workspace: Path, manifest: dict[str, Any], execute: Execute,
           limits: Limits) -> PolicyReceipt:
    build, functional = manifest.get("build", {}), manifest.get("functional", {})
    compilers = manifest.get("portability", {}).get("compilers", ["g++", "clang++"])
    sources, test_source = build.get("sources", []), functional.get("test_source")
    if not isinstance(compilers, list) or len(compilers) < 2 or not sources or not isinstance(test_source, str):
        return policy("G07", "INVALID", "PORTABILITY_CONTRACT_MISSING")
    runs: list[dict[str, object]] = []
    for index, compiler in enumerate(compilers):
        binary = f".gv2/portability_{index}"
        command = [str(compiler), f"-std={build.get('standard', 'c++17')}",
                   *(str(value) for value in build.get("flags", [])), "-I.",
                   *(str(value) for value in sources), test_source,
                   *(f"-l{value}" for value in build.get("libraries", [])), "-o", binary]
        compiled = execute(command, workspace, limits, None)
        if compiled.launch_error or compiled.timed_out:
            return policy("G07", "INVALID", "PORTABILITY_TOOLCHAIN_UNAVAILABLE",
                          compiler=compiler, compile=result_facts(compiled))
        if compiled.returncode != 0:
            return policy("G07", "FAIL", "PORTABILITY_BUILD_FAIL",
                          compiler=compiler, compile=result_facts(compiled))
        run = execute([f"./{binary}"], workspace, limits, None)
        runs.append({"compiler": compiler, "compile": result_facts(compiled), "run": result_facts(run)})
        if run.launch_error:
            return policy("G07", "INVALID", "PORTABILITY_RUNTIME_UNAVAILABLE", runs=runs)
        if run.timed_out or run.returncode != 0:
            return policy("G07", "FAIL", "PORTABILITY_FUNCTIONAL_FAIL", runs=runs)
    return policy("G07", "PASS", "PORTABILITY_PASS", runs=runs)
